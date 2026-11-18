import os


def resolve_model(key):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.txt")
    table = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        table[parts[0]] = parts[1]
    if key in table:
        return table[key]
    if "/" in key:
        return key
    raise SystemExit("unknown model '%s'. choices: %s" % (key, ", ".join(table)))


PREAMBLE = """
from typing import *
from bisect import *
from collections import *
from copy import *
from datetime import *
from heapq import *
from math import *
from re import *
from string import *
from random import *
from itertools import *
from functools import *
from operator import *
import string, re, datetime, collections, heapq, bisect, copy, math, random, itertools, functools, operator


class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right


def list_node(values):
    head = ListNode(0)
    cur = head
    for v in values:
        cur.next = ListNode(v)
        cur = cur.next
    return head.next


def linked_list_to_list(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out


def is_same_list(a, b):
    return linked_list_to_list(a) == linked_list_to_list(b)


def tree_node(values):
    if not values:
        return None
    root = TreeNode(values[0])
    q = deque([root])
    i = 1
    while q and i < len(values):
        node = q.popleft()
        if i < len(values) and values[i] is not None:
            node.left = TreeNode(values[i])
            q.append(node.left)
        i += 1
        if i < len(values) and values[i] is not None:
            node.right = TreeNode(values[i])
            q.append(node.right)
        i += 1
    return root


def tree_to_list(root):
    out = []
    q = deque([root])
    while q:
        node = q.popleft()
        if node:
            out.append(node.val)
            q.append(node.left)
            q.append(node.right)
        else:
            out.append(None)
    while out and out[-1] is None:
        out.pop()
    return out


def is_same_tree(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return a.val == b.val and is_same_tree(a.left, b.left) and is_same_tree(a.right, b.right)
"""
