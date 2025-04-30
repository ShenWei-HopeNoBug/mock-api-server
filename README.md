## 项目 python 版本 v3.8.9

### 初始化 package.txt 包版本

`pip freeze > package.txt`

### 更新 requirements.txt 依赖

`pipreqs ./`

### 命令行启动抓包服务

`mitmdump -s request_catch.py`

### 打包命令

#### 不带黑窗

`pyinstaller -F -w main.py`

#### 带黑窗

`pyinstaller -F main.py`

### 查看被 LFS 追踪的所有文件
`git lfs ls-files`
