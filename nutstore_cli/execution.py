# encoding: utf-8
import re
from os import path
from itertools import ifilter

import click
import tabulate
from dateutil.parser import parse as dt_parse
from parsimonious import ParseError
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

from nutstore_cli.utils import output
from nutstore_cli.client.exceptions import WebdavException

HELP = """
cd: Change working directory
    $ cd {absolute_remote_path}
    $ cd {relative_remote_path}

download: Download remote file to a temp local path 
    $ download {remote_file_name}
    
exit: Exit the interface

help: Show help 

ls: List remote file in working directory
    $ ls 
    $ ls | grep {keyword}
    
rm: Remove remote file
    $ rm {remote_file_name}

upload: Upload local file to remote 
    $ upload {local_file_path}
"""

COMMANDS = ['cd', 'download', 'exit', 'grep', 'help', 'ls', 'rm', 'upload']

RULES = r"""
    command     = cd / ls / exit / help / download / upload / rm

    rm          = "rm" _ string
    upload      = "upload" _ string
    download    = "download" _ string _ (string)?
    help        = "help" / "h" / "?"
    exit        = "exit" / "quit" / "q"
    ls          = ("ls" / "ll") (grep)?
    cd          = _ "cd" _ string _
    
    grep        = pipe "grep" _ ex_string
    
    pipe        = _ "|" _

    ex_string   = string / "*" / "-" / "_" / "."
    string      = char+
    char        = ~r"[^\s'\\]"
    _           = ~r"\s*"
"""

grammar = Grammar(RULES)

ATTRS = (
    lambda f: path.basename(f.name),
    'size',
    lambda f: dt_parse(f.mtime).strftime('%Y-%m-%d %H:%M')
)

LABELS = ('Filename', 'Size', 'Modify Time')


class ExecutionVisitor(NodeVisitor):
    unwrapped_exceptions = (WebdavException,)

    def __init__(self, context):
        """
        :type context: nutstore_cli.cli.Context
        """
        super(ExecutionVisitor, self).__init__()

        self.context = context

    def visit_cd(self, node, children):
        path = children[3].text
        self.context.client.cd(path)

    def visit_exit(self, node, children):
        self.context.should_exit = True

    def visit_ls(self, node, children):
        labels, rows = self.context.client.list(ATTRS, LABELS)
        name_filter = children[1].children[3].text if children[1].children else ''
        rows = ifilter(lambda row: bool(row[0]), rows)
        if name_filter:
            rows = ifilter(lambda row: re.search(name_filter, row[0], flags=re.IGNORECASE), rows)
        rows = list(rows)
        rows.sort(key=lambda row: row[2])  # order by mtime
        output.info(tabulate.tabulate(rows, headers=labels))

    def visit_download(self, node, children):
        cloud_path = children[2].text
        store_path = children[4].text if len(node.children) == 5 else None
        self.context.client.download(cloud_path, store_path)

    def visit_upload(self, node, children):
        local_path = children[2].text
        self.context.client.upload(local_path)

    def visit_rm(self, node, children):
        cloud_path = children[2].text
        if click.confirm('rm {}?'.format(cloud_path)):
            self.context.client.rm(cloud_path)

    def visit_help(self, node, children):
        output.info(HELP)

    def generic_visit(self, node, children):
        if (not node.expr_name) and node.children:
            if len(children) == 1:
                return children[0]
            return children
        return node


def execute(command, context):
    if not command.strip():
        return

    visitor = ExecutionVisitor(context)
    try:
        root = grammar.parse(command)
    except ParseError:
        output.error('Invalid command {0}.'.format(repr(command)))
        return

    try:
        visitor.visit(root)
    except WebdavException as e:
        output.error(str(e))
