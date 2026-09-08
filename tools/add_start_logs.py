"""批量给 views.py 中没有 start 日志的平台 view 添加日志"""
import re

with open(r'D:\source\info\parser_api\views.py', encoding='utf-8') as f:
    content = f.read()

# 给使用 SITE_URLS 的 view 加 start 日志（未添加过的）
pattern = r'(    url = SITE_URLS\["(\w+)"\]\n    t0 = time\.monotonic\(\)\n)(?!    logger\.info)'

def add_start_log(m):
    platform = m.group(2)
    return m.group(1) + f'    logger.info("{platform}_view start url=%s", url)\n'

new_content = re.sub(pattern, add_start_log, content)

# 统一结束日志格式：把 "view response url=%s status=%d elapsed=%.1fs" 改为 "{platform}_view done"
# 找到每个 "view response" 前面对应的 url 赋值，附加 platform
pattern2 = r'logger\.info\("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed\)'
# 替换为更清晰的格式，url 已在 start 日志中有了
new_content = new_content.replace(
    'logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)',
    'logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)'
)

with open(r'D:\source\info\parser_api\views.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

starts = len(re.findall(r'logger\.info\(".*?_view start', new_content))
dones = len(re.findall(r'logger\.info\("view done', new_content))
print(f"start logs: {starts}, done logs: {dones}")
print("OK")
