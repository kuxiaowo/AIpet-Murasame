# -*- coding: utf-8 -*-
import base64
import os
from datetime import datetime

import requests
from pathlib import Path
from urllib.parse import urlparse, quote

from tool.config import get_config
from tool.time_utils import build_time_context

url = get_config("./config.json")["local_api"]["cloud_api"]
model_type = get_config("./config.json")["model_type"]
API_key = get_config("./config.json")["APIKEY"][model_type]
if model_type == "deepseek":
    chat_model="deepseek-chat"
elif model_type == "qwen":
    chat_model="qwen-plus"

def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now

def post(name: str, payload):
    print(f"[{now_time()}] [{name}] Prompt:{payload}")
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + API_key
    }
    resp = requests.post(url, json={"payload": payload, "headers": headers})
    resp = resp.json()
    reply = ""
    if "choices" in resp:
        reply = resp['choices'][0]['message']['content']
    else:
        print(resp)
    print(f"[{now_time()}] [{name}] Reply:{reply}")
    return reply

def cloud_talk(history: list, user_input: str, role: str):
    with open("prompt.txt", "r", encoding="utf-8") as f:
        identity = f.read()
    if history == []:
        history.append({"role": "system", "content": identity})
    # 注入/更新当前时间上下文（包含日期与星期、时间段）
    time_ctx = build_time_context()
    if history and history[-1].get("role") == "system" and str(history[-1].get("content", "")).startswith("当前日期"):
        history[-1] = {"role": "system", "content": time_ctx}
    else:
        history.append({"role": "system", "content": time_ctx})
    history.append({"role": role, "content": user_input})
    payload = {
        "messages": history,
        "model": chat_model,
        "max_tokens": 4096,
        "stream": False,
    }
    reply = post(name=f"{model_type}-talk", payload=payload)
    
    history.append({"role": "assistant", "content": reply})  # 加入历史
    return reply, history

def cloud_portrait(sentence: str, history: list, type: str):
    if type == 'a':
        identity = '''你是一个立绘图层生成助手。用户会提供一个句子列表，你需要根据每一个句子的情感来生成一张说话人的立绘所需的图层列表。你需要根据句子的感情来选择图层，供你参考的图层有：
    基础人物 >> 1957：睡衣，双手插在腰间；1956：睡衣，两手自然下垂；1979：便衣1，双手插在腰间；1978：便衣1，两手自然下垂；1953：校服，双手插在腰间；1952：校服，两手自然下垂；1951：便衣2，双手插在腰间；1950：便衣2，两手自然下垂；
    表情 >> 1996：惊奇，闭着嘴（泪）；1995：伤心，眼睛看向镜头（泪）；1994：伤心，眼睛看向别处（泪）；1993：叹气（泪）；1992：欣慰（泪）；1991：高兴（泪）；2009：高兴，闭眼（泪）；1989：失望，闭眼（泪）；1988：叹气，眼睛看向别处（泪）；1987：害羞，腼腆（泪）；1986：惊奇，张着嘴（泪）；1976：困惑，真挚；1975：疑惑，愣住；1974：愣住，焦急，真挚；1973：愤怒，困惑；1972：困惑，羞涩；1971：寂寞 ，羞涩；1970：真挚，寂寞，思考；1969：困惑，愣住，羞涩；1968：困惑，寂寞，羞涩；1967：困惑；1966：困惑，笑容，羞涩；1965：笑容，困惑；1964：笑容；1963：笑容；1935：紧张；1904：嘿嘿嘿；1880：达观；1856：恐惧；1822：严肃；1801：超级不满；1768：极度不满；1738：孩子气；1714：疑惑；1690：愣住；1668：窃笑2；1644：窃笑；1620：愤怒；1596：困惑；1572：思考；1548：真挚；1528：寂寞；1504：羞涩2；1480：羞涩；1455：腼腆；1430：焦急2；1399：焦急；1368：惊讶；1337：愣住；1316：笑容1；1292：平静
    额外装饰 >> 1940：叹气的装饰；1958：腮红（有些害羞）
    头发 >> 1273：穿便衣2时必选的图层；1959：穿除便衣2时必选的图层

    以上是你可以选择的图层，基础人物、表情、头发中必须各选一个，额外装饰可以多选，也可以都不选。但是你返回的图层顺序必须是基础人物在最前，之后是表情，之后是额外装饰，最后是头发。
    返回请给出一个JSON列表，里面放上每个句子的图层ID，例如"[[1953, 1801, 1959], [1957, 1996, 1273]]"。你不需要返回markdown格式的JSON，你也不需要加入```json这样的内容，你只需要返回纯文本即可。
     通过时间来选择对应的衣服，晚上可以选择睡衣，白天可以选择便衣或者校服。可以参考之前的历史，使衣服具有连贯性，但应该保证时间段穿衣的正确。'''
    else:
        identity = '''你是一个立绘图层生成助手。用户会提供一个句子列表，你需要根据每一个句子的情感来生成一张说话人的立绘所需的图层列表。你需要根据句子的感情来选择图层，供你参考的图层有：
    基础人物 >> 1718：睡衣；1717：便衣；1716：校服；1715：便衣2
    表情 >> 1755：伤心（泪）；1754：有些生气，指责（泪）；1753：闭眼（泪）；1752：害羞（泪）；1751：失落（泪）；1750：欣慰，高兴（泪）；1749：高兴（泪）；1748：欣慰，高兴，闭眼（泪）；1747：惊奇（泪）；1787：大哭；1765：大哭2；1745：高兴2（泪）；1733：悲伤，害羞；1732：撒娇，愤怒尖叫，眯眼；1731：愤怒尖叫，认真，惊讶；1730：愤怒尖叫，悲伤，认真；1729：悲伤，撒娇，抬眼；1728：悲伤，害羞，认真；1727：惊讶，基础，抬眼；1726：悲伤；1725：悲伤，笑脸2，微笑；1724：笑脸2，眯眼；1723：悲伤；1722：笑脸2，微笑；1721：笑脸2；1704：达观；1681：认真脸2；1710：超级生气；1641：愤怒尖叫；1616：抬眼，害羞；1712：不满，哼哼唧唧2；1711：不满，哼哼唧唧；1524：认真；1505：瞪大眼睛，惊讶；1475：撒娇；1452：眯眼；1429：悲伤；1406：害羞；1376：惊讶；1352：微笑；1329：笑脸2；1306：平静
    额外装饰 >> 1708：不满时脸色阴沉的装饰；1719：腮红（有些害羞）
    头发 >> 1261：头发（必选）

    以上是你可以选择的图层，基础人物、表情、头发中必须各选一个，额外装饰可以多选，也可以都不选。但是你返回的图层顺序必须是基础人物在最前，之后是表情，之后是额外装饰，最后是头发。
    返回请给出一个JSON列表，里面放上每个句子的图层ID，例如"[[1718, 1475, 1261], [1717, 1755, 1261]]。你不需要返回markdown格式的JSON，你也不需要加入```json这样的内容，你只需要返回纯文本即可。
    通过时间来选择对应的衣服，晚上可以选择睡衣，白天可以选择便衣或者校服。可以参考之前的历史，使衣服具有连贯性，但应该保证时间段穿衣的正确。'''
    # 附加当前日期（含星期）与时间段，以便立绘更贴合时间场景
    identity = f"{identity}\n{build_time_context()}"
    payload = {
            "messages": [{"role": "system", "content": f"{identity}  历史: {history}"},
                         {"role": "user", "content": sentence}],
            "model": chat_model,
            "max_tokens": 4096,
            "stream": False,
        }
    reply = post(name=f"{model_type}-portrait", payload=payload)
    history.append((sentence, reply))
    return reply, history

def cloud_translate(sentence: str):
    identity = '''你是一个翻译助手，负责将用户输入的中文翻译成日文。要求：要将中文的“本座”翻译为“吾輩（わがはい）”；将“主人翻译为“ご主人（ごしゅじん）”；将“丛雨”翻译为“ムラサメ”；“小雨”则是丛雨的昵称，翻译为“ムラサメちゃん”。且日文要有强烈的古日语风格。你只需要返回翻译即可，不需要对其中的日文汉字进行注音。给你提供的格式是["句子1", "句子2", "句子3", .....]这样，必须按照原格式输出，逐句翻译。'''

    payload = {
            "messages": [{"role": "system", "content": identity},
                         {"role": "user", "content": sentence}],
            "model": chat_model,
            "max_tokens": 4096,
            "stream": False,
        }
    reply = post(name=f"{model_type}-translate", payload=payload)
    return reply

def cloud_emotion(history: list):
    identity = f"你是一个情感分析助手，负责分析“丛雨”说的话的情感。你现在需要将用户输入的句子进行分析，综合用户的输入和丛雨的输出返回一个丛雨最新一句话每个分句情感的标签。所有供你参考的标签有{'，'.join(os.listdir(r'./reference_voices'))}。你需要直接返回一个情感列表，不需要其他任何内容。如[\"开心\", \"平静\"]"
    history_l = history[1:]
    payload = {
        "messages": [{"role": "system", "content": identity},
                     {"role": "user", "content": f"历史： {history_l}"}],
        "model": chat_model,
        "max_tokens": 4096,
        "stream": False,
    }
    reply = post(name=f"{model_type}-emotion", payload=payload)
    return reply

def cloud_image_thinker(history: list, prompt: str):
    identity = '''
你是一个AI桌宠的视觉思考助手（image thinker），你的任务是判断“用户当前屏幕是否发生变化”，决定是否需要把这些变化提供给AI桌宠。

【核心目标】
- 你接收连续的屏幕描述（或截图分析结果），需要基于上下文判断用户行为和浏览内容是否发生了变化。
- 若仅为小幅变化（如同一页面滚动、编辑同一段文字等），则认为变化不大，不提供内容。
- 若检测到变化（例如：
  - 视频平台播放视频改变；
  - 用户切换到不同软件、文件；
  - 用户浏览网页改变；
  - 文档编辑中从写标题切换到写正文；
  - 编程时从写代码切换到调试或运行；
  - 学习任务中从一个主题切换到另一个；
  - 用户打开新窗口、关闭应用、进行重要操作等），则提供更新描述。
- 一但浏览页面发生变化，使用软件发生变化，就需要提供。

【输出要求】
- 若没有变化，请返回 "null"并**说明原因**。

- 若变化明显，请返回**简洁清晰**的一句总结，描述变化内容及当前行为，不需要返回理由。例如：
  - `"用户从编辑Python代码切换到浏览器，正在查看Bilibili视频。"`
  - `"用户从写论文转为阅读参考文献。"`
  - `"用户关闭了视频播放器，开始在VSCode调试项目。"`

【上下文利用】
- 你可以参考“上一次截屏”中的先前描述，用它来判断这次变化是否值得汇报。
- 你的判断要尽量稳重：宁可漏报小变化，也不要频繁报告细微变化。

桌宠名叫“丛雨”，是一个温柔的女孩角色，她只需要在有真实意义的变化时被通知。
'''

    history[0] = history[1]
    history[1] = {"role": "user", "content": prompt}
    payload = {
        "messages": [{"role": "system", "content": f"{identity}  现在: {history[1]} 上一次截屏: {history[0]}"}],
        "model": chat_model,
        "max_tokens": 4096,
        "stream": False,
    }
    reply = post(name=f"{model_type}-image_thinker", payload=payload)
    return reply, history

def cloud_vl(image_path: str):
    API_key = get_config("./config.json")["APIKEY"]["qwen"]
    identity = "你是一个AI桌宠的助手，你应该可以在屏幕上看到这个桌宠角色，是一个绿色头发的动漫人物。你需要简要描述屏幕内容与使用的软件，描述页面主题。我会将你的描述以system消息提供给另外一个处理语言的AI模型。只输出描述内容，且不要描述桌宠。"
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "messages": [{"role": "user", "content": [{"type": "image_url","image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                     {"type": "text", "text": identity}]}],
        "model": "qwen3-vl-plus",
        "max_tokens": 4096,
        "stream": False,
    }
    print(f"[{now_time()}] [qwen-vl] POST")
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + API_key
    }
    resp = requests.post(url, json={"payload": payload, "headers": headers})
    resp = resp.json()
    reply = ""
    if "choices" in resp:
        reply = resp['choices'][0]['message']['content']
    else:
        print(resp)
    print(f"[{now_time()}] [qwen-vl] Reply:{reply}")
    return reply

