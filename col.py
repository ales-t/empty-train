#!/usr/bin/env python3
import sys
import os
import signal
from traceback import print_exc
from subprocess import Popen, PIPE
from threading import Thread
from queue import SimpleQueue
from typing import Optional, TypeVar, List
from functools import wraps


queue = SimpleQueue()


T = TypeVar("T")

def none_throws(optional: Optional[T], message: str = "Unexpected `None`") -> T:
    if optional is None:
        raise AssertionError(message)
    return optional


def exit_on_throw(fn):
	@wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except:
			print_exc(file=sys.stderr)
			os.kill(os.getpid(), signal.SIGKILL)
	return wrapper


def split(column, queue, fin, fout):
	for line in fin:
		fields = line.rstrip(b'\n').split(b'\t')
		queue.put(fields[:column] + fields[(column+1):])
		fout.write(fields[column] + b'\n')
	queue.put(None) # End indicator
	fout.close()


def merge(column, queue, fin, fout):
	for field in fin:
		fields = queue.get()
		if fields is None:
			raise RuntimeError('Subprcess produced more lines of output than it was given.')
		fout.write(b'\t'.join(fields[:column] + [field.rstrip(b'\n')] + fields[column:]) + b'\n')
	if queue.get() is not None:
		raise RuntimeError('Subprocess produced fewer lines than it was given.')
	fout.close()


try:
	column = int(sys.argv[1])

	child = Popen(sys.argv[2:], stdin=PIPE, stdout=PIPE)

	feeder = Thread(target=exit_on_throw(split), args=[column, queue, sys.stdin.buffer, none_throws(child).stdin])
	feeder.start()

	consumer = Thread(target=exit_on_throw(merge), args=[column, queue, none_throws(child).stdout, sys.stdout.buffer])
	consumer.start()

	retval = child.wait()

	feeder.join()
	consumer.join()

	sys.exit(retval)
except SystemExit:
	pass
except FileNotFoundError as e:
	print(e, file=sys.stderr)
	sys.exit(2)
except:
	print_exc(file=sys.stderr)
	sys.exit(127)
