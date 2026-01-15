# -*- coding: utf-8 -*-
from flask import Flask, send_from_directory, jsonify
import os
from pathlib import Path


class AppServer:
  def __init__(self, debug: bool = True, port: int = 5000):
    """
    初始化静态文件服务器
    :param web_root: 静态文件根目录，默认为项目下的app目录
    :param debug: 是否启用调试模式
    :param port: 服务端口号
    """
    self.debug = debug
    self.port = port
    self.web_root: Path = Path(os.path.abspath('./appServer'))
    self.app = Flask('APP_SERVER', root_path=str(self.web_root))
    self._setup_routes()
    self._running = False

  def _setup_routes(self) -> None:
    """设置路由"""

    @self.app.route('/ping', methods=['GET'])
    def ping():
      return jsonify({'data': 'pong!'})

  def _ensure_web_directory(self) -> None:
    """确保app目录存在"""
    if not self.web_root.exists():
      self.web_root.mkdir(parents=True)
      print(f"创建app目录: {self.web_root}")

  def start(self, threaded: bool = True) -> None:
    """
    启动服务器
    :param threaded: 是否以线程方式运行
    """
    self._ensure_web_directory()
    self.app.run(debug=self.debug, port=self.port)

  def stop(self) -> None:
    print('stop')

  def is_running(self) -> bool:
    """检查服务器是否正在运行"""
    return self._running
