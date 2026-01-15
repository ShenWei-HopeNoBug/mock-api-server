# -*- coding: utf-8 -*-
from flask import Flask, send_from_directory, jsonify
import os
import threading
from pathlib import Path
from typing import Optional


class AppServer:
  def __init__(self, web_root: str = None, debug: bool = True, port: int = 5000):
    """
    初始化静态文件服务器
    :param web_root: 静态文件根目录，默认为项目下的app目录
    :param debug: 是否启用调试模式
    :param port: 服务端口号
    """
    self.debug = debug
    self.port = port
    self.web_root: Path = Path(web_root) if web_root else Path(os.path.abspath('./app'))
    self.app = Flask(__name__, root_path=str(self.web_root))
    self._setup_routes()
    self._server_thread: Optional[threading.Thread] = None
    self._running = False

  def _setup_routes(self) -> None:
    """设置路由"""

    @self.app.route('/ping', methods=['GET'])
    def ping():
      return jsonify({'data': 'pong!'})

    @self.app.route('/app_server/<path:path>')
    def serve_static(path):
      """处理所有静态文件请求"""
      file_path = self.web_root / path

      # 如果路径是目录，尝试查找index.html
      if file_path.is_dir():
        index_path = file_path / 'index.html'
        if index_path.exists():
          return send_from_directory(self.web_root, f"{path}/index.html")
        return "Directory index not found", 404

      # 如果文件存在，返回文件内容
      if file_path.exists() and file_path.is_file():
        return send_from_directory(self.web_root, path)

      # 如果都不存在，返回404
      return "File not found", 404

  def _ensure_web_directory(self) -> None:
    """确保web目录存在"""
    if not self.web_root.exists():
      self.web_root.mkdir(parents=True)
      print(f"已创建web目录: {self.web_root}")
      self._create_default_index()

  def _create_default_index(self) -> None:
    """创建默认的index.html文件"""
    index_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Welcome</title>
            <style>body{font-family: Arial, sans-serif; text-align: center; margin-top: 50px;}</style>
        </head>
        <body>
            <h1>Welcome to Static File Server</h1>
            <p>Place your static files in the 'web' directory.</p>
        </body>
        </html>
        """
    (self.web_root / 'index.html').write_text(index_content, encoding='utf-8')

  def start(self, threaded: bool = True) -> None:
    """
    启动服务器
    :param threaded: 是否以线程方式运行
    """
    self._ensure_web_directory()
    print(f"静态文件根目录: {self.web_root}")

    if threaded:
      self._running = True
      self._server_thread = threading.Thread(
        target=lambda: self.app.run(debug=self.debug, port=self.port, use_reloader=False)
      )
      self._server_thread.daemon = True
      self._server_thread.start()
      print(f"服务器已在后台线程中启动，访问地址: http://localhost:{self.port}")
    else:
      self.app.run(debug=self.debug, port=self.port)

  def stop(self) -> None:
    """停止服务器"""
    if self._server_thread and self._running:
      # 注意：Flask开发服务器没有提供优雅的停止方法
      # 在生产环境中应该使用WSGI服务器如Gunicorn或uWSGI
      self._running = False
      # 强制终止线程（不推荐，但Flask开发服务器没有提供更好的方法）
      # 在生产环境中应该使用更好的服务器管理方式
      print("正在停止服务器...")
      import os
      import signal
      os.kill(os.getpid(), signal.SIGINT)

  def is_running(self) -> bool:
    """检查服务器是否正在运行"""
    return self._running


def main():
  # 示例用法
  server = AppServer(debug=True, port=5000)
  try:
    server.start(threaded=False)
  except KeyboardInterrupt:
    print("\n服务器已停止")


if __name__ == '__main__':
  main()
