# 运行与复现

在项目根目录创建环境，安装requirements-lock.txt。测试使用tests中的明确标记样例，不依赖个人目录、原始下载文件或Power BI缓存。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

恢复[数据来源](data_sources.md)后执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_analysis
.\.venv\Scripts\python.exe -m scripts.prepare_powerbi
```

默认分析基准日为2026-10-22，支持 `python -m scripts.run_analysis --as-of YYYY-MM-DD`。数据更新后保留新旧快照，不把旧标价当成实时有效报价。

prepare_powerbi生成10张CSV并将当前项目目录写入Power BI的ProjectRoot参数。随后打开dashboard/powerbi/ProcurementIntelligence.pbip，执行刷新。也可在Power Query参数管理中修改ProjectRoot。首次使用需先恢复数据，仓库不含.pbi缓存；[模型与刷新说明](../dashboard/powerbi/README.md)列出各表和验证查询。

当前程序仅绑定127.0.0.1。上传文件不写入原始数据目录，不发送到外部服务。端口占用时可使用 `--server.port=8502`。CSV/XLSX最大20MB，字段类型和缺失约束见数据字典。

原始数据、data/processed、dashboard/powerbi/input、网页证据、环境和本地日志均被.gitignore排除。需要完整证据核对时，应获取原始快照或重新合法采集对应观察，不能用空目录冒充验证成功。
