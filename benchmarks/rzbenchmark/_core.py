import statistics
from collections import defaultdict
from sys import getsizeof
from timeit import default_timer
from types import BuiltinFunctionType, FunctionType, MethodType
from typing import Any, Iterable, Optional, Tuple, Union

from ._defs import (
    AnyCallee,
    AnyInData,
    ByDataReport,
    CallableAny,
    Report,
    ReportItem,
    Summary,
    SummaryItem,
)


class Estimator:

    def __call__(self, callee: CallableAny, data: Any, count_of_call: int) -> float:
        with Estimator.Elapsed() as elapsed:
            for _ in range(count_of_call):
                callee(data)
        return elapsed()

    class Elapsed:
        __slots__ = '_start', 'dx'

        FLOAT_FMT = '.3f'

        def __init__(self):
            self._start = 0
            self.dx = 0

        def __enter__(self):
            self._start = default_timer()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.dx = default_timer() - self._start

        def __call__(self, fmt=None) -> Union[float, str]:
            return self.dx if fmt is None else format(self.dx, fmt)


class ByDataSummary:

    def __init__(self):
        self.by_data_ratios = defaultdict(list)

    def __call__(self, by_data_report: ByDataReport):
        for x in by_data_report:
            self.by_data_ratios[x.callee_name].append(x.ratio)

    def calc_summary(self) -> Summary:
        ret = []
        for callee_name, ratios in self.by_data_ratios.items():
            ret.append(SummaryItem(
                callee_name=callee_name,
                mean=statistics.mean(ratios),
                median=statistics.median(ratios)
            ))
        ret.sort(key=lambda x: x.median)
        return ret


class NameGenerator:

    def __init__(self):
        self._i = 1
        self._name_counters = defaultdict(int)

    def __call__(self, obj: CallableAny):
        ret = self.scan_name(obj)
        if not ret:
            ret = 'callable'

        if ret in self._name_counters:
            count = self._name_counters[ret] + 1
            ret = ret + '-' + str(count)
            self._name_counters[ret] = count
        else:
            self._name_counters[ret] = 1
        return ret

    @classmethod
    def scan_name(cls, x):
        ret = None
        if isinstance(x, (BuiltinFunctionType, FunctionType, MethodType)):
            ret = str(x)
            if ret.startswith('<bound method '):
                ret = ret[14:ret.find(' of <')]  # <bound method [NAME] of <*>>
            else:
                ret = ret[10:ret.find(' at ')]  # <function [NAME] at *>
                if '<lambda>' in ret:
                    ret = 'lambda'
            if '<locals>.' in ret:
                ret = ret[ret.find('<locals>.') + 9:]
        return ret


def benchmark(callees: Iterable[AnyCallee],  # pylint: disable=too-many-branches
              dataset: Iterable[AnyInData],
              *,
              count_factor=1.0,
              estimator=None,
              summary=None,
              name_generator=None,
              verbose=True) -> Tuple[Report, Optional[Any]]:
    """
    :param callees:
    :param dataset:
    :param count_factor:
    :param estimator: Default is Estimator()
    :param summary: None, False or summary object, default is ByDataSummary()
    :param name_generator:
    :param verbose:
    :return:
    """

    # pylint: disable=too-many-arguments, too-many-locals
    if not estimator:
        estimator = Estimator()
    if summary is None:
        summary = ByDataSummary()
    if not name_generator:
        name_generator = NameGenerator()
    ret = {}

    for data_name, data, count_of_call in dataset:
        count_of_call = round(count_of_call * count_factor)
        if verbose:
            print(data_name, 'count of call:', count_of_call, 'size of data:', getsizeof(data))

        if count_of_call <= 0:
            continue
        group = []
        for callee_data in callees:
            if not callable(callee_data):
                callee_name, callee = callee_data
            else:
                callee_name, callee = name_generator(callee_data), callee_data

            if verbose:
                print(' -', callee_name)

            elapsed = estimator(callee, data, count_of_call)
            group.append(ReportItem(callee_name=callee_name, elapsed=elapsed))

        group.sort(key=lambda x: x.elapsed)
        first = group[0]
        for item in group:
            item.ratio = item.elapsed / first.elapsed

        if summary:
            summary(group)
        ret[data_name] = group

    if verbose:
        print()

    return ret, summary.calc_summary() if summary else None
