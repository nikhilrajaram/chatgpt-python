import os

from chatgpt import Conversation
from chatgpt.cmd_parse import CmdParse


def main():
    conversation = Conversation()
    CmdParse(conversation=conversation).cmdloop()

if __name__ == '__main__':
    main()
