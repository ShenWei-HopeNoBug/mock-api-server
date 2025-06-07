# -*- coding: utf-8 -*-
import os
import webbrowser
import pandas as pd
import json
from lib.decorate import error_catch
from config.work_file import (MITMPROXY_DATA_PATH, USER_API_DATA_PATH)
from lib.utils_lib import JsonFormat


@error_catch(error_msg='读取 mitmproxy api 数据失败', error_return=[])
def get_mitmproxy_api_data_list(work_dir='.'):
  api_list = []
  # 数据源地址
  mitmproxy_data_path = '{}{}'.format(work_dir, MITMPROXY_DATA_PATH)
  # 读取抓包数据
  if os.path.exists(mitmproxy_data_path):
    data = pd.read_json(mitmproxy_data_path)

    # 行遍历
    for row_index, row_data in data.iterrows():
      api_list.append({
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
