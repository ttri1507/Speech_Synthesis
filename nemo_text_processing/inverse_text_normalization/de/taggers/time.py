# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
# Copyright 2015 and onwards Google, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from nemo_text_processing.inverse_text_normalization.de.taggers.cardinal import CardinalFst
from nemo_text_processing.inverse_text_normalization.de.utils import get_abs_path
from nemo_text_processing.inverse_text_normalization.de.graph_utils import (
    GraphFst,
    convert_space,
    delete_extra_space,
    delete_space,
    insert_space,
)
from pynini.lib.pynutil import insert

try:
    import pynini
    from pynini.lib import pynutil

    PYNINI_AVAILABLE = True
except (ModuleNotFoundError, ImportError):
    PYNINI_AVAILABLE = False


class TimeFst(GraphFst):
    """
    Finite state transducer for classifying time
        e.g. twelve thirty -> time { hours: "12" minutes: "30" }
        e.g. twelve past one -> time { minutes: "12" hours: "1" }
        e.g. two o clock a m -> time { hours: "2" suffix: "a.m." }
        e.g. quarter to two -> time { hours: "1" minutes: "45" }
        e.g. quarter past two -> time { hours: "2" minutes: "15" }
        e.g. half past two -> time { hours: "2" minutes: "30" }
    """

    def __init__(self):
        super().__init__(name="time", kind="classify")
        # hours, minutes, seconds, suffix, zone, style, speak_period

        time_zone = pynini.invert(pynini.string_file(get_abs_path("data/time/time_zone.tsv")))
        hour_to = pynini.string_file(get_abs_path("data/time/hour_to.tsv"))
        minute_to = pynini.string_file(get_abs_path("data/time/minute_to.tsv"))
        hour = pynini.string_file(get_abs_path("data/time/hour.tsv"))
        minute = pynini.string_file(get_abs_path("data/time/minute.tsv"))
        half = pynini.cross("halb", "30")
        quarters = pynini.cross("viertel", "15") | pynini.cross("drei viertel", "45")

        # only used for < 1000 thousand -> 0 weight
        cardinal = pynutil.add_weight(CardinalFst().graph_no_exception, weight=-0.7)
        oclock = pynutil.delete("uhr")

        final_graph_hour = pynutil.insert("hours: \"") + hour + pynutil.insert("\"")
        # "[..] uhr (zwanzig)"
        final_graph_minute = (
            oclock
            + pynutil.insert("minutes: \"")
            + (pynutil.insert("00") | delete_space + minute)
            + pynutil.insert("\"")
        )
        final_time_zone_optional = pynini.closure(
            delete_space + insert_space + pynutil.insert("zone: \"") + convert_space(time_zone) + pynutil.insert("\""),
            0,
            1,
        )

        # vier uhr
        # vier uhr zehn
        # vierzehn uhr zehn
        graph_hm = final_graph_hour + delete_extra_space + final_graph_minute

        # 10 nach vier, vierzehn nach vier, viertel nach vier
        graph_m_nach_h = (
            pynutil.insert("minutes: \"")
            + pynini.union(minute + pynini.closure(delete_space + pynutil.delete("minuten"), 0, 1), quarters)
            + pynutil.insert("\"")
            + delete_space
            + pynutil.delete("nach")
            + delete_extra_space
            + pynutil.insert("hours: \"")
            + hour
            + pynutil.insert("\"")
        )

        # 10 vor vier,  viertel vor vier
        graph_m_vor_h = (
            pynutil.insert("minutes: \"")
            + pynini.union(minute + pynini.closure(delete_space + pynutil.delete("minuten"), 0, 1), quarters)
            @ minute_to
            + pynutil.insert("\"")
            + delete_space
            + pynutil.delete("vor")
            + delete_extra_space
            + pynutil.insert("hours: \"")
            + hour @ hour_to
            + pynutil.insert("\"")
        )

        # viertel zehn,  drei viertel vier, halb zehn
        graph_mh = (
            pynutil.insert("minutes: \"")
            + pynini.union(half, quarters)
            + pynutil.insert("\"")
            + delete_extra_space
            + pynutil.insert("hours: \"")
            + hour @ hour_to
            + pynutil.insert("\"")
        )

        final_graph = ((graph_hm | graph_mh | graph_m_vor_h | graph_m_nach_h) + final_time_zone_optional).optimize()

        final_graph = self.add_tokens(final_graph)

        self.fst = final_graph.optimize()
