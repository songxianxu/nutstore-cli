# encoding: utf-8
import click
from parsimonious import ParseError
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

grammar = Grammar(r"""
    command     = cd / ls / exit / help / download / upload / rm

    rm      = "rm" _ string
    upload      = "upload" _ string
    download    = "download" _ string _ (string)?
    help        = "h" / "help" / "?" / "usage"
    exit        = "exit"
    ls          = "ls" / "ll"
    cd          = _ "cd" _ string _

    string      = char*
    char        = ~r"[^\s'\\]"
    _           = ~r"\s*"
""")


class ExecutionVisitor(NodeVisitor):
    def __init__(self, context):
        """
        :type context: nuts.Context
        """
        super(ExecutionVisitor, self).__init__()

        self.context = context
        self.output = Output()

    def visit_cd(self, node, children):
        path = children[3].text
        self.context.client.cd(path)

    def visit_exit(self, node, children):
        self.context.should_exit = True

    def visit_ls(self, node, children):
        files = self.context.client.formatted_ls()
        self.output.write('\n'.join(files))

    def visit_download(self, node, children):
        cloud_path = children[2].text
        store_path = children[4].text if len(node.children) == 5 else None
        self.context.client.download(cloud_path, store_path)

    def visit_upload(self, node, children):
        local_path = children[2].text
        self.context.client.upload(local_path)

    def visit_rm(self, node, children):
        cloud_path = children[2].text
        self.context.client.rm(cloud_path)

    def visit_help(self, node, children):
        self.output.write("""
        - cd {dir}
        - upload {local_path} {cloud_dir}
        - download {cloud_file} {local_path}
        - mkdir {cloud_dir}
        - rm {cloud_file}
        - exit
        """)

    def generic_visit(self, node, children):
        if (not node.expr_name) and node.children:
            if len(children) == 1:
                return children[0]
            return children
        return node


class Output(object):
    def write(self, data):
        return click.secho(data, fg='green')


def execute(command, context):
    if not command.strip():
        click.secho('Empty command.'.format(command), fg='red')
        return

    visitor = ExecutionVisitor(context)
    try:
        root = grammar.parse(command)
    except ParseError:
        click.secho('Invalid command [{}].'.format(command), fg='red')
    else:
        visitor.visit(root)
