# -*- coding: utf-8 -*-
import os
import time
from typing import Any, Dict
from flask import Flask, jsonify
from pathlib import Path
from lib.decorate import create_thread, error_catch
from lib.logger_lib import APP_LOGGER
from app_types.app_gui_types import AppServerRunningData
from multiprocessing import Process
from lib.utils_lib import (
  check_local_connection,
  is_local_server_running,
  shutdown_local_server,
)


class AppServer:
  def __init__(self, port: int = 5050) -> None:
    self.port: int = port
    self.web_root: Path = Path(os.path.abspath('./appServer'))

  def _ensure_web_directory(self) -> None:
    """确保app目录存在"""
    if not self.web_root.exists():
      self.web_root.mkdir(parents=True)
      print(f"创建app目录: {self.web_root}")

  @create_thread
  def start(self) -> None:
    self._ensure_web_directory()
    app = Flask('APP_SERVER', root_path=str(self.web_root))

    @app.route('/ping', methods=['GET'])
    def ping():
      return jsonify({'data': 'pong!'})

    @app.route('/system/shutdown', methods=['GET'])
    def server_shutdown():
      @create_thread(daemon=True)
      def delayed_shutdown():
        APP_LOGGER.info('APP_SERVER 服务收到 shutdown 指令！正在关闭服务...')
        time.sleep(0.5)
        self.shutdown()

      delayed_shutdown()
      return jsonify({'data': 'shutting down'})

    app.run(host='0.0.0.0', port=self.port, threaded=True)

  def shutdown(self) -> None:
    result = is_local_server_running(
      port=self.port,
      retry=20,
      retry_condition='NOT_RUNNING',
      caller='APP_SERVER_SHUTDOWN',
    )
    if result:
      APP_LOGGER.info(f"即将关闭 APP_SERVER 服务！port={self.port}")
      shutdown_local_server(port=self.port)


# app 服务进程启动
def start_app_server_process(server_config: Dict[str, Any]) -> None:
  port = server_config.get('port', 5050)
  app_server = AppServer(port=port)
  app_server.start()


# 启动并检查 APP_SERVER 服务
@error_catch(error_msg='start_app_server 准备启动 APP_SERVER 异常', error_return={"success": False, "port": 5050})
def start_app_server() -> AppServerRunningData:
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
  max_port_attempts = 100
  attempts = 0
  while check_local_connection(ip='0.0.0.0', port=app_server_port):
    APP_LOGGER.warning(f"APP_SERVER 待启动服务端口被占用: {app_server_port}")
    app_server_port += 1
    attempts += 1
    if attempts >= max_port_attempts:
      APP_LOGGER.error(f"APP_SERVER 连续 {max_port_attempts} 个端口均被占用，无法启动服务！")
      return {"success": False, "port": app_server_port}

  APP_LOGGER.info(f"APP_SERVER 准备启动: prot {app_server_port}")

  _start_server(port=app_server_port)
  time.sleep(1)
  result: bool = is_local_server_running(port=app_server_port, retry=20, caller='APP_SERVER_START')

  if not result:
    APP_LOGGER.error(f"APP_SERVER 准备启动失败! port={app_server_port}")

  return {"success": result, "port": app_server_port}
