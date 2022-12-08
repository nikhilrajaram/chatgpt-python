import json
import os
from typing import List
from urllib.error import HTTPError
from uuid import uuid4 as uuid

import tls_client
from tls_client.sessions import TLSClientExeption

from .errors import ChatgptError, ChatgptErrorCodes


class HTTPSession:
    def __init__(self, timeout=None):
        self._session = tls_client.Session(client_identifier="chrome_107")
        self._timeout = timeout

    def request(self, *args, headers={}, **kwargs):
        send_headers = {
            "Host": "ask.openai.com",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://chat.openai.com/"
        }
        send_headers.update(headers)
        response = self._session.execute_request(
            *args, headers=send_headers, timeout_seconds=self._timeout, **kwargs)
        if response.status_code == 200:
            return response
        else:
            raise HTTPError(args[1], response.status_code,
                            response.text, response.headers, None)


class OpenAIAuthentication:
    def __init__(self, session: HTTPSession):
        self.session = session

    def get_session(self):
        try:
            response = self.session.request(
                "GET", "https://chat.openai.com/api/auth/session", headers={
                    "Host": "ask.openai.com",
                    "Referer": "https://chat.openai.com/chat",
                })
            return response.json()
        except HTTPError as e:
            raise ChatgptError(
                "Error getting the session. You may have a wrong access token; try to login again or insert an access_token yourself.",
                ChatgptErrorCodes.LOGIN_ERROR) from e


class Conversation:
    DEFAULT_MODEL_NAME = "text-davinci-002-render"

    _access_token: str = None
    _conversation_id: str = None
    _parent_message_id: str = None
    _model_name: str = DEFAULT_MODEL_NAME
    _session: HTTPSession = None
    _openai_authentication: OpenAIAuthentication = None

    def __init__(
        self,
        access_token: str = None,
        conversation_id: str = None,
        parent_message_id: str = None,
        timeout: int = None
    ):
        if access_token is not None:
            self._access_token = access_token
        else:
            self._access_token = os.environ['CHATGPT_ACCESS_TOKEN']

        if self._conversation_id is None:
            self._conversation_id = conversation_id

        if self._parent_message_id is None:
            self._parent_message_id = parent_message_id

        self._session = HTTPSession(timeout=timeout)
        self._openai_authentication = OpenAIAuthentication(self._session)

    def __remove_none_values(self, d):
        if not isinstance(d, dict):
            return d
        new_dict = {}
        for k, v in d.items():
            if v is not None:
                new_dict[k] = self.__remove_none_values(v)
        return new_dict

    def get_session(self):
        session_info = self._openai_authentication.get_session()
        self._access_token = session_info["accessToken"]
        return session_info

    def chat(self, message: List[str]):
        if self._parent_message_id is None:
            self._parent_message_id = str(uuid())

        if isinstance(message, str):
            message = [message]

        if self._access_token is None:
            raise ChatgptError(
                "Access token is not provided. Please, provide an access_token through the CHATGPT_ACCESS_TOKEN environment variable", ChatgptErrorCodes.INVALID_ACCESS_TOKEN)

        self._message_id = str(uuid())

        url = "https://chat.openai.com/backend-api/conversation"
        payload = {
            "action": "next",
            "messages": [
                {
                    "id": self._message_id,
                    "role": "user",
                    "content": {
                            "content_type": "text",
                            "parts": message
                    }
                }
            ],
            "conversation_id": self._conversation_id,
            "parent_message_id": self._parent_message_id,
            "model": self._model_name
        }
        payload = json.dumps(self.__remove_none_values(payload))
        try:
            response = self._session.request(
                "POST", url, data=payload, headers={
                    "Authorization": "Bearer {}".format(self._access_token),
                    "Content-Type": "application/json",
                })
            payload = response.text
            last_item = payload.split(("data:"))[-2]
            result = json.loads(last_item)
            self._parent_message_id = self._message_id
            self._conversation_id = result["conversation_id"]
            text_items = result["message"]["content"]["parts"]
            text = "\n".join(text_items)
            postprocessed_text = text.replace(r"\n+", "\n")
            return postprocessed_text

        except HTTPError as ex:
            exception_message = "Unknown error"
            exception_code = ChatgptErrorCodes.UNKNOWN_ERROR
            error_code = ex.code
            if error_code in [401, 409]:
                exception_message = "Please, provide a new access_token through the constructorthrough the CHATGPT_ACCESS_TOKEN environment variable"
                exception_code = ChatgptErrorCodes.INVALID_ACCESS_TOKEN

            elif error_code == 403:
                exception_message = str(ex.msg).split(
                    "h2>")[1].split("<")[0]

            elif error_code == 500:
                exception_message = ex.msg

            else:
                try:
                    exception_message = json.loads(ex.msg)["detail"]
                except ValueError:
                    exception_message = ex.msg

        except TLSClientExeption as ex:
            exception_message = str(ex)
            exception_code = ChatgptErrorCodes.TIMEOUT_ERROR

        except Exception as e:
            exception_message = str(e)
            exception_code = ChatgptErrorCodes.UNKNOWN_ERROR

        raise ChatgptError(
            exception_message, exception_code)

    def reset(self):
        self._message_id = None
        self._parent_message_id = None
        self._conversation_id = None
