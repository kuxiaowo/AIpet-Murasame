# -*- coding: utf-8 -*-
import os
from datetime import datetime

import requests

from tool.config import get_config

url = get_config("./config.json")["local_api"]["deepseek_api"]
API_key = get_config("./APIkey.json")["APIKEY"]

def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now

def deepseek_post(name: str, payload):
    print(f"[{now_time()}] [{name}] Prompt:{payload}")
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + API_key
    }
    resp = requests.post(url, json={"payload": payload, "headers": headers})
    resp = resp.json()
    reply = resp['choices'][0]['message']['content']
    print(f"[{now_time()}] [{name}] Reply:{reply}")
    return reply

def deepseek_talk(history: list, user_input: str, role: str):
    with open("prompt.txt", "r", encoding="utf-8") as f:
        identity = f.read()
    if history == []:
        history.append({"role": "system", "content": identity})
    history.append({"role": role, "content": user_input})
    payload = {
        "messages": history,
        "model": "deepseek-chat",
        "max_tokens": 4096,
        "stream": False,
    }
    reply = deepseek_post(name="deepseek-talk", payload=payload)
    history.append({"role": "assistant", "content": reply})  # 加入历史
    return reply, history

def deepseek_portrait(sentence: str, history: list, type: str):
    if type == 'a':
        identity = '''你是一个立绘图层生成助手。用户会提供一个句子列表，你需要根据每一个句子的情感来生成一张说话人的立绘所需的图层列表。你需要根据句子的感情来选择图层，供你参考的图层有：
    基础人物 >> 1957：睡衣，双手插在腰间；1956：睡衣，两手自然下垂；1979：便衣1，双手插在腰间；1978：便衣1，两手自然下垂；1953：校服，双手插在腰间；1952：校服，两手自然下垂；1951：便衣2，双手插在腰间；1950：便衣2，两手自然下垂；
    表情 >> 1996：惊奇，闭着嘴（泪）；1995：伤心，眼睛看向镜头（泪）；1994：伤心，眼睛看向别处（泪）；1993：叹气（泪）；1992：欣慰（泪）；1991：高兴（泪）；2009：高兴，闭眼（泪）；1989：失望，闭眼（泪）；1988：叹气，眼睛看向别处（泪）；1987：害羞，腼腆（泪）；1986：惊奇，张着嘴（泪）；1976：困惑，真挚；1975：疑惑，愣住；1974：愣住，焦急，真挚；1973：愤怒，困惑；1972：困惑，羞涩；1971：寂寞 ，羞涩；1970：真挚，寂寞，思考；1969：困惑，愣住，羞涩；1968：困惑，寂寞，羞涩；1967：困惑；1966：困惑，笑容，羞涩；1965：笑容，困惑；1964：笑容；1963：笑容；1935：紧张；1904：嘿嘿嘿；1880：达观；1856：恐惧；1822：严肃；1801：超级不满；1768：极度不满；1738：孩子气；1714：疑惑；1690：愣住；1668：窃笑2；1644：窃笑；1620：愤怒；1596：困惑；1572：思考；1548：真挚；1528：寂寞；1504：羞涩2；1480：羞涩；1455：腼腆；1430：焦急2；1399：焦急；1368：惊讶；1337：愣住；1316：笑容1；1292：平静
    额外装饰 >> 1940：叹气的装饰；1958：腮红（有些害羞）
    头发 >> 1273：穿便衣2时必选的图层；1959：穿除便衣2时必选的图层

    以上是你可以选择的图层，基础人物、表情、头发中必须各选一个，额外装饰可以多选，也可以都不选。但是你返回的图层顺序必须是基础人物在最前，之后是表情，之后是额外装饰，最后是头发。
    返回请给出一个JSON列表，里面放上每个句子的图层ID，例如"[[1953, 1801, 1959], [1957, 1996, 1273]]"。你不需要返回markdown格式的JSON，你也不需要加入```json这样的内容，你只需要返回纯文本即可。可以参考之前的历史，使衣服具有连贯性。'''
    else:
        identity = '''你是一个立绘图层生成助手。用户会提供一个句子列表，你需要根据每一个句子的情感来生成一张说话人的立绘所需的图层列表。你需要根据句子的感情来选择图层，供你参考的图层有：
    基础人物 >> 1718：睡衣；1717：便衣；1716：校服；1715：便衣2
    表情 >> 1755：伤心（泪）；1754：有些生气，指责（泪）；1753：闭眼（泪）；1752：害羞（泪）；1751：失落（泪）；1750：欣慰，高兴（泪）；1749：高兴（泪）；1748：欣慰，高兴，闭眼（泪）；1747：惊奇（泪）；1787：大哭；1765：大哭2；1745：高兴2（泪）；1733：悲伤，害羞；1732：撒娇，愤怒尖叫，眯眼；1731：愤怒尖叫，认真，惊讶；1730：愤怒尖叫，悲伤，认真；1729：悲伤，撒娇，抬眼；1728：悲伤，害羞，认真；1727：惊讶，基础，抬眼；1726：悲伤；1725：悲伤，笑脸2，微笑；1724：笑脸2，眯眼；1723：悲伤；1722：笑脸2，微笑；1721：笑脸2；1704：达观；1681：认真脸2；1710：超级生气；1641：愤怒尖叫；1616：抬眼，害羞；1712：不满，哼哼唧唧2；1711：不满，哼哼唧唧；1524：认真；1505：瞪大眼睛，惊讶；1475：撒娇；1452：眯眼；1429：悲伤；1406：害羞；1376：惊讶；1352：微笑；1329：笑脸2；1306：平静
    额外装饰 >> 1708：不满时脸色阴沉的装饰；1719：腮红（有些害羞）
    头发 >> 1261：头发（必选）

    以上是你可以选择的图层，基础人物、表情、头发中必须各选一个，额外装饰可以多选，也可以都不选。但是你返回的图层顺序必须是基础人物在最前，之后是表情，之后是额外装饰，最后是头发。
    返回请给出一个JSON列表，里面放上每个句子的图层ID，例如"[[1718, 1475, 1261], [1717, 1755, 1261]]。你不需要返回markdown格式的JSON，你也不需要加入```json这样的内容，你只需要返回纯文本即可。可以参考之前的历史，使衣服具有连贯性。'''
    payload = {
            "messages": [{"role": "system", "content": f"{identity}  历史: {history}"},
                         {"role": "user", "content": sentence}],
            "model": "deepseek-chat",
            "max_tokens": 4096,
            "stream": False,
        }
    reply = deepseek_post(name="deepseek-portrait", payload=payload)
    history.append((sentence, reply))
    return reply, history

def deepseek_translate(sentence: str):
    identity = '''你是一个翻译助手，负责将用户输入的中文翻译成日文。要求：要将中文的“本座”翻译为“吾輩（わがはい）”；将“主人翻译为“ご主人（ごしゅじん）”；将“丛雨”翻译为“ムラサメ”；“小雨”则是丛雨的昵称，翻译为“ムラサメちゃん”。且日文要有强烈的古日语风格。你只需要返回翻译即可，不需要对其中的日文汉字进行注音。给你提供的格式是["句子1", "句子2"]这样，必须按照原格式输出，逐句翻译。'''

    payload = {
            "messages": [{"role": "system", "content": identity},
                         {"role": "user", "content": sentence}],
            "model": "deepseek-chat",
            "max_tokens": 4096,
            "stream": False,
        }
    reply = deepseek_post(name="deepseek-translate", payload=payload)
    return reply

def deepseek_emotion(history: list):
    identity = f"你是一个情感分析助手，负责分析“丛雨”说的话的情感。你现在需要将用户输入的句子进行分析，综合用户的输入和丛雨的输出返回一个丛雨最新一句话每个分句情感的标签。所有供你参考的标签有{'，'.join(os.listdir(r'./reference_voices'))}。你需要直接返回一个情感列表，不需要其他任何内容。如[\"开心\", \"平静\"]"
    history_l = history[1:]
    payload = {
        "messages": [{"role": "system", "content": identity},
                     {"role": "user", "content": f"历史： {history_l}"}],
        "model": "deepseek-chat",
        "max_tokens": 4096,
        "stream": False,
    }
    reply = deepseek_post(name="deepseek-emotion", payload=payload)
    return reply

def deepseek_image_thinker(history: list, prompt: str):
    identity = '''你现在是一个思考助手，来协助一个AI丛雨桌宠工作。你需要根据我提供给你的屏幕描述，来决定这段描述是否有必要提供给AI桌宠进行处理。我提供的历史是根据时间顺序依次提供，最早的在前，最新的在后。如果历史只有一个那么可以选择不提供。
    根据上下文判断，只要用户正在专注的事发生了改变就需要提供，如果没有发生改变则可以不提供。
    你需要详细描述用户的行为变化，说明用户具体做了什么操作，但是描述要尽可能精练，不要太长。
    这个桌宠是一个绿色头发的小女孩，名叫丛雨。
   若你觉得需要提供，那么请回复具体描述内容以及进行的操作。
    '''
    # 若你觉得不需要提供给AI桌宠，那么请回复“null”。
    history.append({"role": "user", "content": prompt})
    payload = {
        "messages": [{"role": "system", "content": f"{identity}  历史: {history}"}],
        "model": "deepseek-chat",
        "max_tokens": 4096,
        "stream": False,
    }
    reply = deepseek_post(name="deepseek-image_thinker", payload=payload)
    history.append({"role": "assistant", "content": reply})
    return reply, history

if __name__ == '__main__':
    sentence = "今天一大早我就跑去学校准备参加社团活动，可是天突然下起了大雨，我没带伞只能在教学楼门口躲雨，偏偏这个时候你走过来递给我一把伞，还笑着说“主人，别淋湿了”，害得我一下子脸红心跳得厉害。"
    #history = [("", "[1950, 1368, 1958]")]
    #reply, history= deepseek_portrait(sentence, history, "a")
    reply = '''["主人、小雨……嗯……嘻嘻……嘿嘿……嘻嘻嘻……啊哈哈哈哈！", "我喜欢你"]'''
    history = [{"role": "user", "content": "小雨。。"},
               {"role": "assistant", "content": reply}]
    reply = deepseek_portrait(reply, history=[], type="a")
    print(reply)
