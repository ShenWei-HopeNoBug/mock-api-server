# Mock API Server

## 环境要求

- Python 3.13.15

## 快速开始

### 安装依赖

```bash
pip install -r package.txt
```

### 更新依赖

**初始化 package.txt（导出当前环境已安装的全部包）：**

```bash
pip freeze > package.txt
```

**更新 requirements.txt（扫描代码中实际 import 的第三方包）：**

```bash
python gen_requirements.py
```

输出到指定文件：

```bash
python gen_requirements.py -o package.txt
```

## 工具命令

### 命令行启动抓包服务

```bash
mitmdump -s request_catch.py
```

### 打包

运行项目目录中的 `build.py` 脚本进行打包：

```bash
python build.py
```

### 查看被 LFS 追踪的所有文件

```bash
git lfs ls-files
```