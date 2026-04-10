from typing import List, Dict, Optional, Iterator, Union
from openai import OpenAI


class ParateraQwenClient:
    def __init__(
        self,
        api_key: str = "sk-8F9nSuW9y5_BgSwwdiMvHQ",
        base_url: str = "https://llmapi.paratera.com/v1/",
        model_name: str = "Qwen3-30B-A3B-Instruct-2507",
        max_tokens: int = 16384,
    ):
        """
        Paratera OpenAI-compatible Qwen 客户端

        :param api_key: API Key
        :param base_url: OpenAI-compatible base_url（包含 /v1）
        :param model_name: 模型名称
        :param max_tokens: 默认最大输出 token（直接 16k）
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/") + "/",
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.8,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Union[str, Iterator[str]]:
        """
        多轮对话接口
        """
        max_tokens = max_tokens or self.max_tokens

        if not stream:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        else:
            return self._stream_chat(
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

    def _stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> Iterator[str]:
        """
        内部方法：处理流式输出
        """
        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    def simple_chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Union[str, Iterator[str]]:
        """
        单轮对话快捷方法（固定 16k 输出）
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        return self.chat(messages, **kwargs)
