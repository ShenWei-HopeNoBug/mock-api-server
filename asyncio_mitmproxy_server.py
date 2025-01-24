# -*- coding: utf-8 -*-
import asyncio
from time import sleep

from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from multiprocessing import Process, Manager
from request_catch import RequestRecorder
import global_var


async def config_mitmproxy(host='0.0.0.0', port=8080):
  """配置 mitmproxy 参数与启动"""
  options = Options(listen_host=host, listen_port=port)
  request_recorder = RequestRecorder(use_history=False)
  addons = [request_recorder]

  # 创建 DumpMaster 实例
  master = DumpMaster(options)
  master.addons.add(*addons)
  # 把 master 实例挂在脚本实例上，用于内部条件触发关闭 master 服务
  request_recorder.mitmproxy_master = master

  try:
    print('启动 mitmproxy 主循环...')
    # 启动 mitmproxy 主循环
    await master.run()

    # 主循环退出，重置下抓包结束信号
    global_var.update_global_var(key='mitmproxy_stop_signal', value=False)
    print('停止 mitmproxy 主循环')
  except KeyboardInterrupt:
    print('error: mitmproxy 主循环 shutdown!')
    master.shutdown()  # 当手动中断时，关闭 master


def run_mitmproxy(host='0.0.0.0', port=8080):
  """运行 mitmproxy"""
  loop = asyncio.new_event_loop()
  asyncio.set_event_loop(loop)
  loop.run_until_complete(config_mitmproxy(host, port))
  loop.close()


def start_mitmproxy(host='0.0.0.0', port=8080) -> Process:
  """启动 mitmproxy"""
  print("Start Mitmproxy")
  mitmproxy_process = Process(target=run_mitmproxy, args=(host, port,))
  mitmproxy_process.start()
  print("Mitmproxy is running")
  return mitmproxy_process

# 强杀进程退出服务
def stop_mitmproxy(process: Process) -> None:
  """停止 mitmproxy"""
  if process:
    process.terminate()
    process.join()
  print('Mitmproxy Normal Exit')


# -------------- 调试
def test():
  mitmproxy_process = start_mitmproxy(host='0.0.0.0', port=8080)  # 启动 mitmproxy
  sleep(10)
  stop_mitmproxy(mitmproxy_process)


if __name__ == '__main__':
  test()
