#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" processors.py
Description:
"""
__author__ = "Anthony Fong"
__copyright__ = "Copyright 2021, Anthony Fong"
__credits__ = ["Anthony Fong"]
__license__ = ""
__version__ = "0.1.0"
__maintainer__ = "Anthony Fong"
__email__ = ""
__status__ = "Prototype"

# Default Libraries #
import asyncio
import copy
import multiprocessing
import multiprocessing.connection
from multiprocessing import Process, Pool, Lock, Event, Queue, Pipe
import warnings
import time
import typing

# Downloaded Libraries #
import advancedlogging
from advancedlogging import AdvancedLogger, ObjectWithLogging
from baseobjects import StaticWrapper, TimeoutWarning

# Local Libraries #


# Definitions #
# Functions #
def run_method(obj, method, **kwargs):
    return getattr(obj, method)(**kwargs)


# Classes #
# Processing #
# Todo: Add automatic closing to release resources automatically
class SeparateProcess(ObjectWithLogging, StaticWrapper):
    """A wrapper for Process which adds restarting and passing a method to be run in a separate process.

    Class Attributes:
        CPU_COUNT (int): The number of CPUs this computer has.
        class_loggers (:obj:`dict` of :obj:`AdvancedLogger`): The loggers for this class.

    Attributes:
        name (str): The name of this object.
        daemon (bool): Determines if the separate process will continue after the main process exits.
        target: The function that will be executed by the separate process.
        args: The arguments for the function to be run in the separate process.
        kwargs: The keyword arguments for the function to be run the in the separate process.
        method_wrapper: A wrapper function which executes a method of an object.
        _process (:obj:`Process`): The Process object that this object is wrapping.

    Args:
        target: The function that will be executed by the separate process.
        name: The name of this object.
        args: The arguments for the function to be run in the separate process.
        kwargs: The keyword arguments for the function to be run the in the separate process.
        daemon (bool): Determines if the separate process will continue after the main process exits.
        delay (bool): Determines if the Process will be constructed now or later.
        init (bool): Determines if this object will construct.
    """
    _wrapped_types = [Process(daemon=True)]
    _wrap_attributes = ["_process"]
    CPU_COUNT = multiprocessing.cpu_count()
    class_loggers = {"separate_process": AdvancedLogger("separate_process")}

    # Construction/Destruction
    def __init__(self, target=None, name="", args=(), kwargs={}, daemon=None, delay=False, init=True):
        super().__init__()
        self.method_wrapper = run_method

        self._process = None

        if init:
            self.construct(target, name, args, kwargs, daemon, delay)

    @property
    def target(self):
        """The function that will be executed by the separate process, gets from _process."""
        return self._target

    @target.setter
    def target(self, value):
        self._target = value

    @property
    def args(self):
        """The arguments for the function to be run in the separate process, gets from _process."""
        return self._args

    @args.setter
    def args(self, value):
        self._args = tuple(value)

    @property
    def kwargs(self):
        """The keyword arguments for the function to be run the in the separate process, get from _process."""
        return self._kwargs

    @kwargs.setter
    def kwargs(self, value):
        self._kwargs = dict(value)

    # Pickling
    def __getstate__(self):
        """Creates a dictionary of attributes which can be used to rebuild this object.

        Returns:
            dict: A dictionary of this object's attributes.
        """
        out_dict = self.__dict__.copy()
        process = out_dict["__process"]
        if process:
            kwargs = {"target": process._target,
                      "name": process._name,
                      "args": process._args,
                      "kwargs": process._kwargs}
            try:
                kwargs["daemon"] = process.daemon
            except AttributeError:
                pass
        else:
            kwargs = None

        out_dict["new_process_kwargs"] = kwargs
        out_dict["__process"] = None

        return out_dict

    def __setstate__(self, in_dict):
        """Builds this object based on a dictionary of corresponding attributes.

        Args:
            in_dict (dict): The attributes to build this object from.
        """
        process_kwargs = in_dict.pop("new_process_kwargs")
        self.__dict__ = in_dict
        if process_kwargs:
            self.create_process(**process_kwargs)

    # Constructors
    def construct(self, target=None, name=None, args=(), kwargs={}, daemon=None, delay=False):
        """Constructs this object.

        Args:
            target: The function that will be executed by the separate process.
            name: The name of this object.
            args: The arguments for the function to be run in the separate process.
            kwargs: The keyword arguments for the function to be run the in the separate process.
            daemon (bool): Determines if the separate process will continue after the main process exits.
            delay (bool): Determines if the Process will be constructed now or later.
        """
        if name is not None:
            self.name = name

        # Create process if not delayed
        if not delay:
            self.create_process(target, name, args, kwargs, daemon)
        # Stash the attributes until a new process is made
        else:
            if target is not None:
                self._target = target

            if name is not None:
                self._name = name

            if args:
                self._args = tuple(args)

            if kwargs:
                self._kwargs = dict(kwargs)

            if daemon:
                self.daemon = daemon

    # State
    def is_alive(self):
        """Checks if the process is running."""
        if self._process is None:
            return False
        else:
            return self._process.is_alive()

    # Process
    def create_process(self, target=None, name=None, args=(), kwargs={}, daemon=None):
        """Creates a Process object to be stored within this object.

        Args:
            target: The function that will be executed by the separate process.
            name: The name of this object.
            args: The arguments for the function to be run in the separate process.
            kwargs: The keyword arguments for the function to be run the in the separate process.
            daemon (bool): Determines if the separate process will continue after the main process exits.
        """
        # Get previous attributes
        if self._process is not None:
            if target is None:
                try:
                    target = self._target
                except AttributeError:
                    pass
            if daemon is None:
                daemon = self.daemon
            if not args:
                args = self._args
            if not kwargs:
                kwargs = self._kwargs

        # Create new Process
        self._process = Process()

        # Set attributes after stashed attributes are set.
        if name is not None:
            self._process.name = name
        if target is not None:
            self._process._target = target
        if daemon is not None:
            self._process.daemon = daemon
        if args:
            self._process._args = args
        if kwargs:
            self._process._kwargs = kwargs

    def set_process(self, process):
        """Set this object's process to a new one.

        Args:
            process (:obj:`Process`): The new process.
        """
        self._process = process

    # Target
    def target_object_method(self, obj, method, args=(), kwargs={}):
        """Set the target to be a method of an object.

        Args:
            obj: The object the method will be executed from.
            method (str): The name of the method in the object.
            args: Arguments to be used by the method.
            kwargs: The keywords arguments to be used by the method.
        """
        kwargs["obj"] = obj
        kwargs["method"] = method
        self.create_process(target=self.method_wrapper, args=args, kwargs=kwargs)

    # Execution
    def start(self):
        """Starts running the process."""
        self.trace_log("separate_process", "start", "spawning new process...", name=self.name, level="DEBUG")
        try:
            self._process.start()
        except:
            self.create_process()
            self._process.start()

    def join(self, timeout=None):
        """Wait fpr the process to return/exit.

        Args:
            timeout (float, optional): The time in seconds to wait for the process to exit.
        """
        self._process.join(timeout)
        if self._process.exitcode is None:
            warnings.warn(TimeoutWarning("'join_async'"), stacklevel=2)

    async def join_async(self, timeout=None, interval=0.0):
        """Asynchronously, wait for the process to return/exit.

        Args:
            timeout (float, optional): The time in seconds to wait for the process to exit.
            interval (float, optional): The time in seconds between each queue query.
        """
        start_time = time.perf_counter()
        while self._process.exitcode is None:
            await asyncio.sleep(interval)
            if timeout is not None and (time.perf_counter() - start_time) >= timeout:
                warnings.warn(TimeoutWarning("'join_async'"), stacklevel=2)
                return

    def join_async_task(self, timeout=None, interval=0.0):
        """Creates an asyncio task which waits for the process to return/exit.

        Args:
            timeout (float): The time in seconds to wait for termination.
            interval (float): The time in seconds between termination checks. Zero means it will check ASAP.
        """
        return asyncio.create_task(self.join_async(timeout, interval))

    def restart(self):
        """Restarts the process."""
        if isinstance(self._process, Process):
            if self._process.is_alive():
                self._process.terminate()
        self.create_process()
        self._process.start()

    def close(self):
        """Closes the process and frees the resources."""
        if isinstance(self._process, Process):
            if self._process.is_alive():
                self._process.terminate()
            self._process.close()


class ProcessingUnit(ObjectWithLogging, StaticWrapper):
    _wrapped_types = [None]
    _wrap_attributes = ["_task_object"]
    class_loggers = {"processor_root": AdvancedLogger("processor_root")}
    DEFAULT_TASK = None

    # Construction/Destruction
    def __init__(self, name=None, task=None, to_kwargs={},
                 separate_process=False, daemon=False, p_kwargs={},
                 allow_setup=False, allow_closure=False, init=True):
        super().__init__()
        self.name = name
        self.unit_setup_kwargs = {}
        self.unit_closure_kwargs = {}
        self.allow_setup = allow_setup
        self.allow_closure = allow_closure
        self.await_closure = False

        self.separate_process = separate_process
        self._is_processing = False
        self.process = None
        self.processing_pool = None

        self._execute_setup = self.setup
        self._task_object = None
        self._execute_closure = self.closure
        self._joined = True

        if init:
            self.construct(name=name, task=task, to_kwargs=to_kwargs, daemon=daemon, p_kwargs=p_kwargs)

    @property
    def task_object(self):
        if self.is_processing():
            warnings.warn()
        return self._task_object

    @task_object.setter
    def task_object(self, value):
        if self.is_processing():
            warnings.warn()
        self._task_object = value

    # Constructors
    def construct(self, name=None, task=None, to_kwargs={}, daemon=False, p_kwargs={}):
        if self.separate_process:
            self.new_process(name=name, daemon=daemon, kwargs=p_kwargs)
        if task is None:
            if self.task_object is None:
                self.default_task_object(**to_kwargs)
        else:
            self.task_object = task

    # State
    def is_async(self):
        if asyncio.iscoroutinefunction(self._execute_setup) or asyncio.iscoroutinefunction(self._execute_closure):
            return True
        elif not self.separate_process and self.task_object.is_async():
            return True
        else:
            return False

    def is_processing(self):
        if self.process is not None and self.separate_process:
            self._is_processing = self.process.is_alive()
        return self._is_processing

    # Process
    def new_process(self, name=None, daemon=False, kwargs={}):
        if name is None:
            name = self.name
        self.process = SeparateProcess(name=name, daemon=daemon, kwargs=kwargs)

    def set_process(self, process):
        self.process = process

    # Set Task Object
    def default_task_object(self, **kwargs):
        self.task_object = self.DEFAULT_TASK(name=self.name, **kwargs)

    # Setup
    def setup(self):
        self.trace_log("processor_root", "setup", "setup method not overridden", name=self.name, level="DEBUG")

    # Closure
    def closure(self):
        self.trace_log("processor_root", "closure", "closure method not overridden", name=self.name, level="DEBUG")

    # Normal Execution Methods
    def run_normal(self, s_kwargs={}, t_kwargs={}, c_kwargs={}):
        self._joined = False
        kwargs = {"s_kwargs": s_kwargs, "t_kwargs": t_kwargs, "c_kwargs": c_kwargs}
        # Optionally run Setup
        if self.allow_setup:
            self.trace_log("processor_root", "run_normal", "running setup", name=self.name, level="DEBUG")
            self._execute_setup(**self.unit_setup_kwargs)

        # Run Task
        if self.separate_process:
            self.trace_log("processor_root", "run_normal", "running task in separate process",
                           name=self.name, level="DEBUG")
            self.process.target_object_method(self.task_object, "run", kwargs=kwargs)
            self.process.start()
        else:
            self.trace_log("processor_root", "run_normal", "running task", name=self.name, level="DEBUG")
            self.task_object.run(**kwargs)

        # Optionally run Closure
        if self.allow_closure:
            self.trace_log("processor_root", "run_normal", "waiting for process to join (blocking)",
                           name=self.name, level="DEBUG")
            if self.separate_process:
                if self.await_closure:
                    self.process.join()
                else:
                    warnings.warn("Run Though! Process could still be running", self.name)
            self.trace_log("processor_root", "run_normal", "running closure", name=self.name, level="DEBUG")
            self._execute_closure(**self.unit_closure_kwargs)
        self._joined = True

    def start_normal(self, s_kwargs={}, t_kwargs={}, c_kwargs={}):
        self._joined = False
        kwargs = {"s_kwargs": s_kwargs, "t_kwargs": t_kwargs, "c_kwargs": c_kwargs}
        # Optionally run Setup
        if self.allow_setup:
            self.trace_log("processor_root", "start_normal", "running setup", name=self.name, level="DEBUG")
            self._execute_setup(**self.unit_setup_kwargs)

        # Run Task
        if self.separate_process:
            self.trace_log("processor_root", "start_normal", "starting task in separate process",
                           name=self.name, level="DEBUG")
            self.process.target_object_method(self.task_object, "start", kwargs=kwargs)
            self.process.start()
        else:
            self.trace_log("processor_root", "start_normal", "starting task", name=self.name, level="DEBUG")
            self.task_object.start(**kwargs)

        # Optionally run Closure
        if self.allow_closure:
            self.trace_log("processor_root", "start_normal", "waiting for process to join (blocking)",
                           name=self.name, level="DEBUG")
            if self.separate_process:
                if self.await_closure:
                    self.process.join()
                else:
                    warnings.warn("Run Though! Process could still be running")
            self.trace_log("processor_root", "start_normal", "running closure", name=self.name, level="DEBUG")
            self._execute_closure(**self.unit_closure_kwargs)
        self._joined = True

    # Async Execute Methods
    async def run_coro(self, s_kwargs={}, t_kwargs={}, c_kwargs={}):
        self._joined = False
        kwargs = {"s_kwargs": s_kwargs, "t_kwargs": t_kwargs, "c_kwargs": c_kwargs}
        # Optionally run Setup
        if self.allow_setup:
            if asyncio.iscoroutinefunction(self._execute_setup):
                self.trace_log("processor_root", "run_coro", "running async setup", name=self.name, level="DEBUG")
                await self._execute_setup(**self.unit_setup_kwargs)
            else:
                self.trace_log("processor_root", "run_coro", "running setup", name=self.name, level="DEBUG")
                self._execute_setup(**self.unit_setup_kwargs)

        # Todo: replace logs from here
        # Run Task
        if self.separate_process:
            self.loggers["processor_root"].debug(self.traceback_formatting("run_coro", "Running task in separate process", self.name))
            self.process.target_object_method(self.task_object, "run", kwargs=kwargs)
            self.process.start()
        else:
            if self.task_object.is_async():
                self.loggers["processor_root"].debug(self.traceback_formatting("run_coro", "Running async task", self.name))
                await self.task_object.run_coro(**kwargs)
            else:
                self.loggers["processor_root"].debug(self.traceback_formatting("run_coro", "Running task", self.name))
                self.task_object.run(**kwargs)

            # Optionally run Closure
            if self.allow_closure:
                if self.separate_process:
                    if self.await_closure:
                        self.loggers["processor_root"].debug(self.traceback_formatting("run_coro", "Awaiting process to join", self.name))
                        await self.process.join_async()
                    else:
                        warnings.warn("Run Though! Process could still be running")
                if asyncio.iscoroutinefunction(self._execute_closure):
                    self.loggers["processor_root"].debug(self.traceback_formatting("run_coro", "Running async closure", self.name))
                    await self._execute_closure(**self.unit_closure_kwargs)
                else:
                    self.loggers["processor_root"].debug(self.traceback_formatting("run_coro", "Running closure", self.name))
                    self._execute_closure(**self.unit_closure_kwargs)
        self._joined = True

    async def start_coro(self, s_kwargs={}, t_kwargs={}, c_kwargs={}):
        self._joined = False
        kwargs = {"s_kwargs": s_kwargs, "t_kwargs": t_kwargs, "c_kwargs": c_kwargs}
        # Optionally run Setup
        if self.allow_setup:
            if asyncio.iscoroutinefunction(self._execute_setup):
                self.loggers["processor_root"].debug(self.traceback_formatting("start_coro", "Running async setup", self.name))
                await self._execute_setup(**self.unit_setup_kwargs)
            else:
                self.loggers["processor_root"].debug(self.traceback_formatting("start_coro", "Running setup", self.name))
                self._execute_setup(**self.unit_setup_kwargs)

        # Run Task
        if self.separate_process:
            self.loggers["processor_root"].debug(self.traceback_formatting("start_coro", "Starting task in separate process", self.name))
            self.process.target_object_method(self.task_object, "start", kwargs=kwargs)
            self.process.start()
        else:
            if self.task_object.is_async():
                self.loggers["processor_root"].debug(self.traceback_formatting("start_coro", "Starting async task", self.name))
                await self.task_object.start_coro(**kwargs)
            else:
                self.loggers["processor_root"].debug(self.traceback_formatting("start_coro", "Starting task", self.name))
                self.task_object.start(**kwargs)

        # Optionally run Closure
        if self.allow_closure:
            if self.separate_process:
                if self.await_closure:
                    self.loggers["processor_root"].debug(self.traceback_formatting("start_coro", "Awaiting process to join", self.name))
                    await self.process.join_async()
                else:
                    warnings.warn("Run though! Process could still be running")
            if asyncio.iscoroutinefunction(self._execute_closure):
                self.loggers["processor_root"].debug(self.traceback_formatting("start_coro", "Running async closure", self.name))
                await self._execute_closure(**self.unit_closure_kwargs)
            else:
                self.loggers["processor_root"].debug(self.traceback_formatting("start_coro", "Running closure", self.name))
                self._execute_closure(**self.unit_closure_kwargs)
        self._joined = True

    # Set Execution Methods
    def set_setup(self, func, kwargs={}):
        if kwargs:
            self.unit_setup_kwargs = kwargs
        self._execute_setup = func

    def use_task_setup(self):
        self.task_object.allow_setup = False
        self._execute_setup = self.task_object.setup

    def set_closure(self, func, kwargs={}):
        if kwargs:
            self.unit_closure_kwargs = kwargs
        self._execute_closure = func

    def use_task_closure(self):
        self.task_object.allow_closure = False
        self._execute_closure = self.task_object.closure

    # Execution
    def run(self, s_kwargs={}, t_kwargs={}, c_kwargs={}):
        if self.is_async():
            asyncio.run(self.run_coro(s_kwargs, t_kwargs, c_kwargs))
        else:
            self.run_normal(s_kwargs, t_kwargs, c_kwargs)

    def run_async_task(self, s_kwargs={}, t_kwargs={}, c_kwargs={}):
        return asyncio.create_task(self.run_coro(s_kwargs, t_kwargs, c_kwargs))

    def start(self, s_kwargs={}, t_kwargs={}, c_kwargs={}):
        if self.is_async():
            asyncio.run(self.start_coro(s_kwargs, t_kwargs, c_kwargs))
        else:
            self.start_normal(s_kwargs, t_kwargs, c_kwargs)

    def start_async_task(self, s_kwargs={}, t_kwargs={}, c_kwargs={}):
        return asyncio.create_task(self.start_coro(s_kwargs, t_kwargs, c_kwargs))

    def join(self, timeout=None):
        start_time = time.perf_counter()
        while not self._joined:
            if timeout is not None and (time.perf_counter() - start_time) >= timeout:
                return None

        if timeout is not None:
            timeout = timeout - (time.perf_counter() - start_time)

        if self.separate_process:
            self.process.join(timeout=timeout)
        return None

    async def join_async(self, timeout=None, interval=0.0):
        start_time = time.perf_counter()
        while not self._joined:
            await asyncio.sleep(interval)
            if timeout is not None and (time.perf_counter() - start_time) >= timeout:
                return None

        if timeout is not None:
            timeout = timeout - (time.perf_counter() - start_time)

        if self.separate_process:
            await self.process.join_async(timeout=timeout, interval=interval)
        return None

    def stop(self, join=True, timeout=None):
        self.loggers["processor_root"].debug(self.traceback_formatting("stop", "Stopping process", self.name))
        self._task_object.stop()
        if join:
            self.join(timeout=timeout)

    async def stop_async(self, join=True, timeout=None, interval=0.0):
        self.loggers["processor_root"].debug(self.traceback_formatting("stop", "Stopping process asynchronously", self.name))
        self._task_object.stop()
        if join:
            await self.join_async(timeout=timeout, interval=interval)

    def reset(self):
        self.task_object.reset()

    def terminate(self):
        if self.separate_process:
            self.process.terminate()


class ProcessingCluster(ProcessingUnit):
    DEFAULT_TASK = None

    # Construction/Destruction
    def __init__(self, name=None, task=None, to_kwargs={},
                 separate_process=False, daemon=False, p_kwargs={},
                 allow_setup=False, allow_closure=False, init=True):
        # Run Parent __init__ but only construct in child
        super().__init__(name=name, task=task, to_kwargs=to_kwargs,
                         separate_process=separate_process, daemon=daemon, p_kwargs=p_kwargs,
                         allow_setup=allow_setup, allow_closure=allow_closure, init=False)

        if init:
            self.construct(name)

    @property
    def execution_order(self):
        return self.task_object.execution_order

    @execution_order.setter
    def execution_order(self, value):
        self.task_object.execution_order = value

    # Container Magic Methods
    def __len__(self):
        return len(self.task_object)

    def __getitem__(self, item):
        return self.task_object[item]

    def __delitem__(self, key):
        del self.task_object[key]

    # Execution
    def stop(self, join=True, timeout=None):
        self.loggers["processor_root"].debug(self.traceback_formatting("stop", "Stopping process", self.name))
        self._task_object.stop(join=join, timeout=timeout)
        if join:
            self.join(timeout=timeout)

    async def stop_async(self, join=True, timeout=None, interval=0.0):
        self.loggers["processor_root"].debug(self.traceback_formatting("stop", "Stopping process asynchronously", self.name))
        self._task_object.stop(join=join, timeout=timeout)
        if join:
            await self.join_async(timeout=timeout, interval=interval)


