### 初始化 package.txt 包版本
pip freeze > package.txt

### 更新 requirements.txt 依赖
pipreqs ./

### 启动抓包服务
mitmdump -s request_catch.py
