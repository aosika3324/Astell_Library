import os
import json
from pathlib import Path

import glob

def check_keys():
    base_dir = r'C:\Users\Administrator\AppData\Roaming\Code\User\globalStorage'
    paths = []
    if os.path.exists(base_dir):
        # 搜寻所有文件夹下的 json
        for root, dirs, files in os.walk(base_dir):
            if 'cline' in root.lower() or 'claude' in root.lower() or 'roo' in root.lower():
                for f in files:
                    if f.endswith('.json'):
                        paths.append(os.path.join(root, f))
                        
    # 再加几个标准候选
    paths.append(r'C:\Users\Administrator\.cline\data\globalState.json')
    paths.append(r'C:\Users\Administrator\AppData\Roaming\Code\User\globalStorage\saoudrizwan.claude-dev\globalState.json')
    paths.append(r'C:\Users\Administrator\AppData\Roaming\Code\User\globalStorage\rooveterinaryinc.roo-cline\globalState.json')

    print("=== 开始搜寻 API Key ===")
    found = False
    for p in paths:
        if os.path.exists(p) and os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 检查根级别的 apiConfiguration (GUI 插件经常放这里)
                    api = data.get('apiConfiguration', {})
                    if not api:
                        # 尝试去读 globalState 里的 apiProvider 等
                        api = data
                        
                    key = api.get('apiKey', 
                          api.get('geminiApiKey', 
                          api.get('openRouterApiKey', 
                          api.get('anthropicApiKey', 'NOT_FOUND'))))
                          
                    if key != 'NOT_FOUND' and key:
                        safe_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
                        print(f"[+] 找到目标! 来源: {p}")
                        print(f"    打码 Key: {safe_key}")
                        print(f"    当前 Provider: {api.get('apiProvider', 'unknown')}")
                        found = True
            except Exception as e:
                print(f"[-] 错误读取 {p}: {e}")
                
    if not found:
        print("[-] 未在标准路径下找到配置。寻找其他可能的 globalState...")

if __name__ == "__main__":
    check_keys()