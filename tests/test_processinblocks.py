#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" test_processinblocks.py
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
import pathlib
import pickle
import time
import timeit

# Downloaded Libraries #
import advancedlogging
import pytest

# Local Libraries #
import src.processingblocks as processingblocks


# Definitions #
# Functions #
@pytest.fixture
def tmp_dir(tmpdir):
    """A pytest fixture that turn the tmpdir into a Path object."""
    return pathlib.Path(tmpdir)


def log(logger, level):
    log_class_ = "separate"
    log_func = "test_trace_log"
    log_str = "Test traceback"
    logger.trace_log(log_class_, log_func, log_str, level=level)
    pass


# Classes #
class ClassTest:
    """Default class tests that all classes should pass."""
    class_ = None
    timeit_runs = 100
    speed_tolerance = 200

    def get_log_lines(self, tmp_dir, logger_name):
        path = tmp_dir.joinpath(f"{logger_name}.log")
        with path.open() as f_object:
            lines = f_object.readlines()
        return lines


class TestSeparateProcess(ClassTest):
    class_ = processingblocks.SeparateProcess

    def test_pickle(self, tmp_dir):
        logger_name = "separate"
        level = "INFO"
        path = tmp_dir.joinpath(f"{logger_name}.log")

        logger = advancedlogging.AdvancedLogger(logger_name)
        logger.setLevel(level)
        logger.add_default_file_handler(path)

        obj = processingblocks.SeparateProcess(target=log, kwargs={"logger": logger, "level": level})
        pickle_jar = pickle.dumps(obj)
        new_obj = pickle.loads(pickle_jar)
        assert set(dir(new_obj)) == set(dir(obj))

    def test_separate_process(self, tmp_dir):
        # Setup
        logger_name = "separate"
        level = "INFO"
        path = tmp_dir.joinpath(f"{logger_name}.log")

        logger = advancedlogging.AdvancedLogger(logger_name)
        logger.setLevel(level)
        logger.add_default_file_handler(path)

        process = processingblocks.SeparateProcess(target=log, kwargs={"logger": logger, "level": level}, delay=True)
        process.construct()
        process.start()

        time.sleep(3)

        assert not process.is_alive()

        # Check log file
        lines = self.get_log_lines(tmp_dir, logger_name)
        count = len(lines)
        assert count == 1
        assert level in lines[0]


class BaseTaskTest(ClassTest):
    class ProduceTask(processingblocks.Task):
        log_path = None

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.number = 0

        def build_loggers(self):
            logger = advancedlogging.AdvancedLogger("TaskTest")
            logger.setLevel("DEBUG")
            logger.add_default_file_handler(self.log_path)
            self.loggers["TaskTest"] = logger
            self.class_loggers["task_root"].add_default_file_handler(self.log_path)
            self.class_loggers["task_root"].setLevel("DEBUG")

        def create_io(self):
            self.outputs.create_queue("RawOut")

        def setup(self):
            self.trace_log("TaskTest", "setup", "Success!")

        async def task_async(self):
            item = self.number
            self.trace_log("TaskTest", "task_async", f"Producing an item {item}")
            self.outputs.send_item("RawOut", item)
            self.trace_log("TaskTest", "task_async", "Item sent")
            self.number += 1
            await asyncio.sleep(2)

    class ModifyTask(processingblocks.Task):
        def build_loggers(self):
            logger = advancedlogging.AdvancedLogger("TaskTest")
            logger.setLevel("DEBUG")
            self.loggers["TaskTest"] = logger

        def link_inputs(self, producer):
            self.inputs.add_queue("RawInput", producer.outputs["RawOut"])

        async def task_async(self):
            thing = await self.inputs.get_item_wait_async("RawInput")
            if thing is None:
                return
            self.trace_log("TaskTest", "task_async", f"Item Received {thing}")
            await asyncio.sleep(2)


class TestTask(BaseTaskTest):
    def test_task(self, tmp_dir):
        logger_name = "task_separate"
        path = tmp_dir.joinpath(f"{logger_name}.log")
        self.ProduceTask.log_path = path
        produce_unit = self.ProduceTask(name="ProduceTask")
        modify_unit = self.ModifyTask(name="ModifyTask")

        modify_unit.link_inputs(produce_unit)

        async def stop():
            await asyncio.sleep(10)
            produce_unit.terminate()
            modify_unit.terminate()

        async def temp_run():
            pro_a_task = produce_unit.start_async_task()
            mod_a_task = modify_unit.start_async_task()
            stop_task = asyncio.create_task(stop())

            await asyncio.gather(pro_a_task, mod_a_task, stop_task)
            print("Success")

        asyncio.run(temp_run())
        assert 1

    def test_separate_process(self, tmp_dir):
        logger_name = "task_separate"
        path = tmp_dir.joinpath(f"{logger_name}.log")
        self.ProduceTask.log_path = path

        produce_unit = self.ProduceTask(name="ProduceTask")
        modify_unit = self.ModifyTask(name="ModifyTask")

        produce_unit.is_process = True
        modify_unit.link_inputs(produce_unit)

        async def stop():
            assert produce_unit.is_processing()
            await asyncio.sleep(10)
            produce_unit.terminate()
            modify_unit.terminate()

        async def temp_run():
            pro_a_task = produce_unit.start_async_task()
            mod_a_task = modify_unit.start_async_task()
            stop_task = asyncio.create_task(stop())

            await asyncio.gather(pro_a_task, mod_a_task, stop_task)
            print("Success")

        asyncio.run(temp_run())
        assert 1


class TestMultiUnitTask(BaseTaskTest):
    class MultiUnitGroup(processingblocks.MultiUnitTask):
        def construct(self, units={}, order=(), **kwargs):
            super().construct(**kwargs)
            produce_unit = TestMultiUnitTask.ProduceTask(name="ProduceTask")
            modify_unit = TestMultiUnitTask.ModifyTask(name="ModifyTask")
            stop_unit = processingblocks.Task(name="Stop")

            async def stop():
                await asyncio.sleep(10)
                produce_unit.terminate()
                modify_unit.terminate()

            produce_unit.is_async = True
            modify_unit.is_async = True
            stop_unit.is_async = True
            modify_unit.link_inputs(produce_unit)
            stop_unit.set_task(stop)

            self.set_unit("ProduceTask", produce_unit, "start")
            self.set_unit("ModifyTask", modify_unit, "start")
            self.set_unit("Stop", stop_unit, "run")

    def test_multi_task(self):
        block = self.MultiUnitGroup(name="Block")
        block.is_async = True
        block.run()
        assert 1


# Main #
if __name__ == '__main__':
    pytest.main(["-v", "-s"])
