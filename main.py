# -*- coding: utf-8 -*-
from mock_server import MockServer


if __name__ == '__main__':
  mock_server = MockServer()

  # 检查和下载静态资源
  mock_server.check_static()

  # 启本地 mock 服务
  mock_server.start_server()
