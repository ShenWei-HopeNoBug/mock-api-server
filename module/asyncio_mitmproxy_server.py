# -*- coding: utf-8 -*-
import asyncio
from typing import Optional
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from multiprocessing import Process
from multiprocessing.synchronize import Event as EventType
from module.request_catch import RequestRecorder
from app_types.mitmproxy_types import MitmproxyRunConfig
from lib.logger_lib import APP_LOGGER


# 轮询停止信号的后台任务
async def _stop_signal_watcher(stop_event: EventType, master: DumpMaster) -> None:
  """每 0.5s 检查 stop_event，检测到后调用 master.shutdown() 优雅关闭"""
  while not stop_event.is_set():
    await asyncio.sleep(0.5)
  print('收到停止信号，正在关闭 mitmproxy 服务...')
  master.shutdown()


# 启动抓包服务task
async def mitmproxy_task(
    mitmproxy_config: MitmproxyRunConfig,
    ready_event: Optional[EventType] = None,
    stop_event: Optional[EventType] = None,
) -> None:
  """配置 mitmproxy 参数与启动"""
  print('mitmproxy_config', mitmproxy_config)
  host = mitmproxy_config.get('host', '0.0.0.0')
  port = mitmproxy_config.get('port', 8080)
  work_dir = mitmproxy_config.get('work_dir', '.')
  mitmproxy_log = mitmproxy_config.get('mitmproxy_log', False)
  options = Options(listen_host=host, listen_port=port)
  request_recorder = RequestRecorder(work_dir=work_dir, stop_event=stop_event, ready_event=ready_event)
  addons = [request_recorder]

  # 创建 DumpMaster 实例
  master = DumpMaster(options, with_termlog=mitmproxy_log, with_dumper=mitmproxy_log)
  master.addons.add(*addons)
  # 把 master 实例挂在脚本实例上，用于内部条件触发关闭 master 服务
  request_recorder.mitmproxy_master = master

  print('启动 mitmproxy 主循环...')

  # 启动停止信号轮询任务
  watcher_task: Optional[asyncio.Task] = None
  if stop_event is not None:
    watcher_task = asyncio.ensure_future(_stop_signal_watcher(stop_event, master))

  try:
    # 启动 mitmproxy 主循环
    await master.run()
  except Exception as e:
    APP_LOGGER.error(f'mitmproxy_task: 启动抓包服务失败！{e}')
    raise
  finally:
    if watcher_task is not None and not watcher_task.done():
      watcher_task.cancel()
    print('mitmproxy 主循环结束！')


# 启动抓包服务
def run_mitmproxy(
    share_dict: MitmproxyRunConfig,
    ready_event: Optional[EventType] = None,
    stop_event: Optional[EventType] = None,
) -> None:
  """运行 mitmproxy"""
  loop = asyncio.new_event_loop()
  asyncio.set_event_loop(loop)
  try:
    loop.run_until_complete(mitmproxy_task(
      mitmproxy_config=share_dict,
      ready_event=ready_event,
      stop_event=stop_event,
    ))
  finally:
    loop.close()


def start_mitmproxy(
    share_dict: MitmproxyRunConfig,
    stop_event: Optional[EventType] = None,
    ready_event: Optional[EventType] = None
) -> Process:
  """启动 mitmproxy"""
  print("Start Mitmproxy")
  mitmproxy_process = Process(target=run_mitmproxy, args=(share_dict, ready_event, stop_event))
  mitmproxy_process.start()
  print("Mitmproxy is running")
  return mitmproxy_process
