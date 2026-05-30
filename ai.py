# app.py - AI作文辅助系统（配置文件版）
import json
import requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import logging
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ====================== 读取配置文件 ======================
CONFIG_PATH = "./config.txt"

def load_config():
    config = {
        "OLLAMA_URL": "http://localhost:8080",
        "MODEL_NAME": "essay-teacher",
        "PORT": 8081
    }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key in config:
                        config[key] = value
        logger.info(f"成功加载配置文件: {CONFIG_PATH}")
    except:
        logger.warning("未找到 config.txt，使用默认配置")
    return config

config = load_config()
OLLAMA_URL = config["OLLAMA_URL"]
MODEL_NAME = config["MODEL_NAME"]
PORT = int(config["PORT"])

# 全局变量存储
user_data = {
    "事情": "",
    "中心": "",
    "大纲": "",
    "素材": "",
    "范文": "",
    "用户作文": ""
}

def call_ollama_stream(prompt):
    """流式调用Ollama API"""
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_predict": 2048,
            "temperature": 0.7,
            "top_p": 0.9
        }
    }
    
    try:
        response = requests.post(url, json=payload, stream=True, timeout=180)
        return response
    except requests.exceptions.Timeout:
        logger.error("Ollama请求超时")
        return "timeout"
    except requests.exceptions.ConnectionError:
        logger.error("无法连接到Ollama服务")
        return "connection_error"
    except Exception as e:
        logger.error(f"Ollama流式调用错误: {e}")
        return str(e)

def call_ollama(prompt):
    """非流式调用Ollama API"""
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=180)
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '')
        else:
            return f"API错误: {response.status_code}"
    except requests.exceptions.Timeout:
        logger.error("Ollama请求超时")
        return "请求超时，请稍后重试"
    except requests.exceptions.ConnectionError:
        logger.error("无法连接到Ollama服务")
        return "无法连接到Ollama服务，请确保Ollama正在运行"
    except Exception as e:
        logger.error(f"Ollama调用错误: {e}")
        return f"连接错误: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/save_event', methods=['POST'])
def save_event():
    data = request.json
    user_data["事情"] = data.get('event', '')
    user_data["中心"] = data.get('center', '')
    return jsonify({"status": "success", "data": user_data})

@app.route('/api/save_essay', methods=['POST'])
def save_essay():
    data = request.json
    user_data["用户作文"] = data.get('essay', '')
    return jsonify({"status": "success", "data": user_data})

@app.route('/api/analyze_essay', methods=['POST'])
def analyze_essay():
    def generate():
        essay = request.json.get('essay', '')
        
        if not essay:
            yield f"data: {json.dumps({'error': '请先输入作文内容'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        prompt = f"""请分析以下作文，提取关键信息：

作文内容：
{essay[:1500]}

请提取：
1. 主要事件：作文中描述的具体事情
2. 中心思想：作文想要表达的主题或感悟

请直接输出JSON格式：
{{"event": "主要事件", "center": "中心思想"}}"""
        
        response = call_ollama_stream(prompt)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务，请确保Ollama正在运行'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"处理响应错误: {e}")
                        continue
        except Exception as e:
            logger.error(f"流式处理错误: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/rewrite_essay', methods=['POST'])
def rewrite_essay():
    def generate():
        essay = request.json.get('essay', '')
        requirement = request.json.get('requirement', '改进作文，使语言更优美')
        
        if not essay:
            yield f"data: {json.dumps({'error': '请先输入作文内容'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        prompt = f"""请根据以下要求改写这篇作文：

原文：
{essay[:1500]}

改写要求：{requirement}

请直接输出改写后的作文："""
        
        response = call_ollama_stream(prompt)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务，请确保Ollama正在运行'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"处理响应错误: {e}")
                        continue
        except Exception as e:
            logger.error(f"流式处理错误: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/outline')
def generate_outline():
    def generate():
        if not user_data["事情"] and not user_data["中心"]:
            yield f"data: {json.dumps({'error': '请先填写事情和中心思想'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        prompt = f"""请为作文生成详细大纲：

事件：{user_data['事情']}
中心思想：{user_data['中心']}

要求：
1. 开头部分：如何引入主题
2. 主体部分：分3-4个段落，每段说明要点
3. 结尾部分：总结升华

请用清晰的层级结构输出大纲："""
        
        response = call_ollama_stream(prompt)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务，请确保Ollama正在运行'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"处理响应错误: {e}")
                        continue
        except Exception as e:
            logger.error(f"流式处理错误: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/material')
def search_material():
    def generate():
        if not user_data["事情"] and not user_data["中心"]:
            yield f"data: {json.dumps({'error': '请先填写事情和中心思想'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        prompt = f"""为以下作文主题搜集素材：

事件：{user_data['事情']}
中心思想：{user_data['中心']}

请提供：
1. 相关名言警句（3-5条）
2. 相关事例（2-3个）
3. 好词好句（5-10个）
4. 写作建议

请分类整理输出："""
        
        response = call_ollama_stream(prompt)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务，请确保Ollama正在运行'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"处理响应错误: {e}")
                        continue
        except Exception as e:
            logger.error(f"流式处理错误: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/fanwen')
def generate_fanwen():
    def generate():
        if not user_data["事情"] and not user_data["中心"]:
            yield f"data: {json.dumps({'error': '请先填写事情和中心思想'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        prompt = f"""请根据以下要求写一篇完整的作文：

事件：{user_data['事情']}
中心思想：{user_data['中心']}

要求：
1. 字数：500-800字
2. 结构完整：开头点题、主体详细描写、结尾升华
3. 语言优美，有真情实感
4. 紧扣中心和事件

请直接输出范文，不要加额外说明："""
        
        response = call_ollama_stream(prompt)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务，请确保Ollama正在运行'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"处理响应错误: {e}")
                        continue
        except Exception as e:
            logger.error(f"流式处理错误: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/correct_errors', methods=['POST'])
def correct_errors():
    def generate():
        text = request.json.get('text', '')
        
        if not text:
            yield f"data: {json.dumps({'error': '没有要检查的文本'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        prompt = f"""请仔细检查以下作文中的错别字和语法错误：

{text[:1500]}

请找出所有错误，并按以下格式输出：
错误位置：[具体词语/句子]
错误类型：[错别字/语法/标点]
修改建议：[正确写法]

如果没有错误，请输出"未发现错误"。"""
        
        response = call_ollama_stream(prompt)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务，请确保Ollama正在运行'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"处理响应错误: {e}")
                        continue
        except Exception as e:
            logger.error(f"流式处理错误: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/polish', methods=['POST'])
def polish_article():
    def generate():
        text = request.json.get('text', '')
        
        if not text:
            yield f"data: {json.dumps({'error': '没有要润色的文本'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        prompt = f"""请对以下作文进行润色，使其更加优美：

{text[:1500]}

润色要求：
1. 优化用词，使语言更生动
2. 调整句式，增强表现力
3. 保持原意不变
4. 增加适当的修辞手法

请直接输出润色后的完整作文："""
        
        response = call_ollama_stream(prompt)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务，请确保Ollama正在运行'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"处理响应错误: {e}")
                        continue
        except Exception as e:
            logger.error(f"流式处理错误: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/auto_write')
def auto_write():
    def generate():
        if not user_data["事情"] and not user_data["中心"]:
            yield f"data: {json.dumps({'error': '请先填写事情和中心思想'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # 1. 生成大纲
        yield f"data: {json.dumps({'type': 'section', 'title': '正在生成大纲...'})}\n\n"
        
        prompt_outline = f"""为作文生成大纲：

事件：{user_data['事情']}
中心思想：{user_data['中心']}

输出格式：1. 开头 2. 主体(分3段) 3. 结尾"""
        
        response = call_ollama_stream(prompt_outline)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'type': 'outline', 'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"大纲生成错误: {e}")
        
        # 2. 搜集素材
        yield f"data: {json.dumps({'type': 'section', 'title': '正在搜集素材...'})}\n\n"
        
        prompt_material = f"""为作文搜集素材：

事件：{user_data['事情']}
中心思想：{user_data['中心']}

提供：
- 名言警句3-5条
- 相关事例2-3个
- 好词好句5-10个
- 写作建议"""
        
        response = call_ollama_stream(prompt_material)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'type': 'material', 'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"素材生成错误: {e}")
        
        # 3. 生成范文
        yield f"data: {json.dumps({'type': 'section', 'title': '正在生成范文...'})}\n\n"
        
        prompt_fanwen = f"""写一篇500-800字的作文。

事件：{user_data['事情']}
中心思想：{user_data['中心']}

要求：
- 开头点题
- 主体详细描写（2-3段）
- 结尾升华主题
- 语言生动优美

直接写作文："""
        
        response = call_ollama_stream(prompt_fanwen)
        
        if isinstance(response, str):
            if response == "timeout":
                yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
            elif response == "connection_error":
                yield f"data: {json.dumps({'error': '无法连接到Ollama服务'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': response})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        data = json.loads(line_str)
                        if 'response' in data and data['response']:
                            yield f"data: {json.dumps({'type': 'fanwen', 'content': data['response']})}\n\n"
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"范文生成错误: {e}")
        
        # 完成
        yield f"data: {json.dumps({'type': 'complete', 'message': '作文生成完成！'})}\n\n"
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True, threaded=True)
