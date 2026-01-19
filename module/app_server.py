# -*- coding: utf-8 -*-
import os
import time
import requests
from flask import Flask, jsonify
from pathlib import Path
from lib.decorate import create_thread, error_catch
from lib.logger_lib import APP_LOGGER
from multiprocessing import Process
from lib.utils_lib import (
  check_local_connection,
  find_connection_process,
  is_local_server_running,
)


class AppServer:
  def __init__(self, port: int = 5050):
    self.port = port
    self.web_root: Path = Path(os.path.abspath('./appServer'))

  def _ensure_web_directory(self) -> None:
    """确保app目录存在"""
    if not self.web_root.exists():
      self.web_root.mkdir(parents=True)
      print(f"创建app目录: {self.web_root}")

  @create_thread
  def start(self) -> None:
    """
    启动服务器
    :param threaded: 是否以线程方式运行
    """
    self._ensure_web_directory()
    app = Flask('APP_SERVER', root_path=str(self.web_root))

    @app.route('/ping')
    def ping():
      return jsonify({'data': 'pong!'})

    @app.route('/system/shutdown')
    def server_shutdown():
      self.stop()

    app.run(host='0.0.0.0', port=self.port, threaded=True)

  def stop(self) -> None:
    process_list = find_connection_process(ip='0.0.0.0', port=self.port)
    if len(process_list) == 0:
      print('未找到 APP_SERVER 进程！port={}'.format(self.port))

    for proc in process_list:
      print('正在关闭 APP_SERVER 进程! port={}'.format(self.port), proc)
      proc.terminate()


# app 服务进程启动
def start_app_server_process(server_config: dict):
  port = server_config.get('port', 5050)
  app_server = AppServer(port=port)
  app_server.start()


# 启动并检查 APP_SERVER 服务
@error_catch(error_msg='start_app_server 准备启动 APP_SERVER 异常', error_return={"success": False, "port": 5050})
def start_app_server() -> dict:
  @create_thread
  def _start_server(port: int = 5050) -> None:
    server_config = {
      "port": port,
    }

    app_server_process = Process(
      target=start_app_server_process,
      args=(server_config,),
      name='app_server_process',
    )

    # 启动进程 APP 服务进程
    app_server_process.start()

  app_server_port = 5050
  while check_local_connection(ip='0.0.0.0', port=app_server_port):
    APP_LOGGER.warning(f"APP_SERVER 待启动服务端口被占用: {app_server_port}")
    app_server_port += 1

  APP_LOGGER.info(f"APP_SERVER 准备启动: prot {app_server_port}")

  _start_server(port=app_server_port)
  time.sleep(1)
  result: bool = is_local_server_running(port=app_server_port, retry=5)

  if not result:
    APP_LOGGER.error(f"APP_SERVER 准备启动失败! port={app_server_port}")

  return {"success": result, "port": app_server_port}
