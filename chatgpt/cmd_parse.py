import cmd

from chatgpt.chatgpt import Conversation


class CmdParse(cmd.Cmd):
    prompt = '> '
    commands = []
    conversation = None

    def __init__(self, conversation: Conversation):
        super(CmdParse, self).__init__()
        self.conversation = conversation
    
    def do_list(self, line):
        print(self.commands)
    
    def default(self, line):
        print(self.conversation.chat(line), end='\n')
        self.commands.append(line)
    
    def do_exit(self, line):
        return True