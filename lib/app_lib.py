# -*- coding: utf-8 -*-
import os
import webbrowser
import pandas as pd
import json
import uuid

from PyQt5.QtWidgets import QMenu
from lib.decorate import error_catch
from config.work_file import (MITMPROXY_DATA_PATH, USER_API_DATA_PATH)
from lib.utils_lib import JsonFormat


# 生成数据的 uuid
def generate_uuid() -> str:
  name = '{}-{}'.format(uuid.uuid4(), uuid.uuid1())
  return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


@error_catch(error_msg='读取 mitmproxy api 数据失败', error_return=[])
def get_mitmproxy_api_data_list(work_dir='.'):
  api_list = []
  # 数据源地址
  mitmproxy_data_path = '{}{}'.format(work_dir, MITMPROXY_DATA_PATH)
  if not os.path.exists(mitmproxy_data_path):
    return []
  # 读取抓包数据
  data = pd.read_json(mitmproxy_data_path)

  # 行遍历
  for row_index, row_data in data.iterrows():
    api_list.append({
      "id": row_data.get('id', ''),
      "type": row_data.get('type'),
      "url": row_data.get('url'),
      "method": row_data.get('method'),
      "params": row_data.get('params'),
      "response": row_data.get('response'),
    })

  return api_list


@error_catch(error_msg='读取 user api 数据失败', error_return=[])
def get_user_api_data_list(work_dir='.'):
  # 读取用户手动 mock 的接口数据
  user_data_path = '{}{}'.format(work_dir, USER_API_DATA_PATH)
  if not os.path.exists(user_data_path):
    return []

  with open(user_data_path, 'r', encoding='utf-8') as fl:
    user_api_list = json.loads(fl.read())
    return user_api_list


@error_catch(error_msg='保存 user api 数据失败', error_return=False)
def save_user_api_data_list(work_dir='.', user_api_list=None) -> bool:
  # 入参校验
  if type(user_api_list) != list:
    return False

  user_data_path = '{}{}'.format(work_dir, USER_API_DATA_PATH)
  if not os.path.exists(user_data_path):
    return False

  with open(user_data_path, 'w', encoding='utf-8') as fl:
    data = JsonFormat.format_dict_to_json_string(user_api_list)
    fl.write(data)

  return True


@error_catch(error_msg='更新 user api 数据失败', error_return=False)
def update_user_api_data(work_dir='.', update_data=None) -> bool:
  # 入参校验
  if type(update_data) != dict:
    return False

  update_id = update_data.get('id', '')
  if not update_id:
    return False

  user_api_list = get_user_api_data_list(work_dir=work_dir)
  index = -1
  # 查找待更新数据
  for i, user_api in enumerate(user_api_list):
    o_id = user_api.get('id', '')
    if update_id == o_id:
      index = i
      break

  if index == -1:
    return False

  o_data = user_api_list[index]
  user_api_list[index] = {
    "id": o_data.get('id'),
    "type": update_data.get('type') or o_data.get('type'),
    "url": update_data.get('url') or o_data.get('url'),
    "method": update_data.get('method') or o_data.get('method'),
    "params": update_data.get('params') or o_data.get('params'),
    "response": update_data.get('response') or o_data.get('response'),
  }

  # 更新数据
  return save_user_api_data_list(work_dir=work_dir, user_api_list=user_api_list)


@error_catch(error_msg='新增 user api 数据失败', error_return=False)
def add_user_api_data(work_dir='.', add_data=None) -> bool:
  if type(add_data) != dict:
    return False

  user_api_list = get_user_api_data_list(work_dir=work_dir)
  data = {
    "id": generate_uuid(),
    "type": add_data.get('type', 'USER'),
    "url": add_data.get('url', ''),
    "method": add_data.get('method', 'GET'),
    "params": add_data.get('params', JsonFormat.format_dict_to_json_string({})),
    "response": add_data.get('response', JsonFormat.format_dict_to_json_string({})),
  }
  user_api_list.append(data)
  return save_user_api_data_list(work_dir=work_dir, user_api_list=user_api_list)


@error_catch(error_msg='删除 user api 数据失败', error_return=False)
def delete_user_api_data(work_dir='.', delete_id: str = '') -> bool:
  if type(delete_id) != str or not delete_id:
    return False

  user_api_list = get_user_api_data_list(work_dir=work_dir)
  index = -1
  # 查找待更新数据
  for i, user_api in enumerate(user_api_list):
    api_id = user_api.get('id', '')
    if api_id == delete_id:
      index = i
      break

  if index == -1:
    return False

  del user_api_list[index]
  return save_user_api_data_list(work_dir=work_dir, user_api_list=user_api_list)


@error_catch(error_msg='读取 api 数据文件失败', error_return=[])
def get_mock_api_data_list(work_dir='.'):
  api_list = get_mitmproxy_api_data_list(work_dir=work_dir)
  api_list.extend(get_user_api_data_list(work_dir=work_dir))

  return api_list


# 加工并打开抓包数据预览html
@error_catch(error_msg='打开抓包数据预览html失败', error_return=False)
def open_mitmproxy_preview_html(root_dir='.', work_dir='.'):
  # 预览数据列表
  preview_list = get_mock_api_data_list(work_dir=work_dir)

  # 把预览数据写入web的静态资源文件
  web_mitmproxy_output_file = r'{}/web/mitmproxy_output.js'.format(root_dir)
  if not os.path.exists(web_mitmproxy_output_file):
    return False
  with open(web_mitmproxy_output_file, 'w', encoding='utf-8') as fl:
    content = "window.MITMPROXY_OUTPUT = {};\n".format(
      JsonFormat.format_dict_to_json_string(preview_list),
    )
    fl.write(content)

  preview_html = r'{}/web/apps/dataPreview/index.html'.format(root_dir)
  if not os.path.exists(preview_html):
    return False
  # 用浏览器打开预览 html 文件
  webbrowser.open(os.path.abspath(preview_html))

  return True


# 打开操作手册
@error_catch(error_msg='打开操作手册html失败', error_return=False)
def open_operation_manual_html(root_dir='.'):
  operation_manual_html = r'{}/web/apps/document/index.html'.format(root_dir)
  if not os.path.exists(operation_manual_html):
    return False
  webbrowser.open(os.path.abspath(operation_manual_html))
  return True


# 修复异常的抓包数据
@error_catch(error_msg='修复异常抓包数据失败', error_return=False)
def fix_user_api_data(work_dir='.') -> bool:
  user_api_list = get_user_api_data_list(work_dir=work_dir)
  update_list = []
  for user_api in user_api_list:
    update_list.append({
      "id": user_api.get('id', generate_uuid()),
      "type": user_api.get('type'),
      "url": user_api.get('url'),
      "method": user_api.get('method'),
      "params": user_api.get('params'),
      "response": user_api.get('response'),
    })

  return save_user_api_data_list(work_dir=work_dir, user_api_list=update_list)


# 批量设置菜单元素禁用状态
@error_catch(error_msg='批量设置菜单元素禁用状态失败')
def set_menu_item_disabled(menu: QMenu, disable_list: list):
  if not menu or not len(disable_list):
    return

  # 构造菜单元素禁用状态字典
  disable_dict: dict = {}
  action_set = set()
  for config in disable_list:
    action_name = config.get('action_name', '')
    disabled = config.get('disabled', False)
    if action_name:
      action_set.add(action_name)
      disable_dict[action_name] = disabled

  actions = menu.actions()
  for action in actions:
    if not len(action_set):
      return

    action_name = action.text()
    # 设置匹配到的菜单的禁用状态
    if action_name in action_set:
      disabled = disable_dict.get(action_name, False)
      action.setEnabled(not disabled)
      action_set.remove(action_name)
