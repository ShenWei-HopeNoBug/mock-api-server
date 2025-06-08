# -*- coding: utf-8 -*-
import asyncio
from time import sleep

from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from multiprocessing import Process
from module.request_catch import RequestRecorder
from lib.decorate import error_catch
from lib.system_lib import GLOBALS_CONFIG_MANAGER


# 启动抓包服务task
@error_catch(error_msg='mitmproxy_task: 启动抓包服务失败！')
async def mitmproxy_task(mitmproxy_config: dict):
  print('mitmproxy_config', mitmproxy_config)
  host = mitmproxy_config.get('host', '0.0.0.0')
  port = mitmproxy_config.get('port', 8080)
  work_dir = mitmproxy_config.get('work_dir', '.')
  use_history = mitmproxy_config.get('use_history', False)
  mitmproxy_log = mitmproxy_config.get('mitmproxy_log', False)
  """配置 mitmproxy 参数与启动"""
  options = Options(listen_host=host, listen_port=port)
  request_recorder = RequestRecorder(use_history=use_history, work_dir=work_dir)
  addons = [request_recorder]

  # 创建 DumpMaster 实例
  master = DumpMaster(options, with_termlog=mitmproxy_log, with_dumper=mitmproxy_log)
  master.addons.add(*addons)
  # 把 master 实例挂在脚本实例上，用于内部条件触发关闭 master 服务
  request_recorder.mitmproxy_master = master

  print('启动 mitmproxy 主循环...')

  # 启动 mitmproxy 主循环
  await master.run()

  # 主循环退出，重置下抓包结束信号
  GLOBALS_CONFIG_MANAGER.set(key='mitmproxy_stop_signal', value=False)
  print('mitmproxy 主循环结束！')


# 启动抓包服务
def run_mitmproxy(share_dict):
  """运行 mitmproxy"""
  loop = asyncio.new_event_loop()
  asyncio.set_event_loop(loop)
  loop.run_until_complete(mitmproxy_task(share_dict))
  loop.close()


def start_mitmproxy(share_dict) -> Process:
  """启动 mitmproxy"""
  print("Start Mitmproxy")
  mitmproxy_process = Process(target=run_mitmproxy, args=(share_dict,))
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
  mitmproxy_config = {
    "host": "0.0.0.0",
    "port": 8080,
    "work_dir": ".",
    "use_history": False,
    "mitmproxy_log": False,
  }
  mitmproxy_process = start_mitmproxy(mitmproxy_config)  # 启动 mitmproxy
  sleep(10)
  stop_mitmproxy(mitmproxy_process)


if __name__ == '__main__':
  test()
