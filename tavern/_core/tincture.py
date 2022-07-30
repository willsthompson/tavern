import inspect
import logging

from tavern._core import exceptions
from tavern._core.extfunctions import get_wrapped_response_function

logger = logging.getLogger(__name__)


class TinctureProvider:
    def __init__(self, tinctures):
        self._tinctures = tinctures
        self._needs_response = None

    def start_tinctures(self, stage):
        results = [t(stage) for t in self._tinctures]
        self._needs_response = []

        for r in results:
            if inspect.isgenerator(r):
                # Store generator and start it
                self._needs_response.append(r)
                next(r)

    def end_tinctures(self, response):
        """
        Send the response object to any tinctures that want it

        Args:
            response (object): The response from 'run' for the stage
        """
        if self._needs_response is None:
            raise RuntimeError(
                "should not be called before accumulating tinctures which need a response"
            )

        for n in self._needs_response:
            try:
                n.send(response)
            except StopIteration:
                pass
            else:
                raise RuntimeError("Tincture had more than one yield")


def get_stage_tinctures(stage, test_spec):
    """Get tinctures for stage

    Args:
        stage (dict): Stage
        test_spec (dict): Whole test spec
    """
    stage_tinctures = []

    def add_tinctures_from_block(maybe_tinctures, blockname):
        logger.debug("Trying to add tinctures from %s", blockname)

        def inner_yield():
            if maybe_tinctures is not None:
                if isinstance(maybe_tinctures, list):
                    for vf in maybe_tinctures:
                        yield get_wrapped_response_function(vf)
                elif isinstance(maybe_tinctures, dict):
                    yield get_wrapped_response_function(maybe_tinctures)
                elif maybe_tinctures is not None:
                    raise exceptions.BadSchemaError(
                        "Badly formatted 'tinctures' block in {}".format(blockname)
                    )

        stage_tinctures.extend(inner_yield())

    add_tinctures_from_block(test_spec.get("tinctures"), "test")
    add_tinctures_from_block(stage.get("tinctures"), "stage")

    logger.debug("%d tinctures for stage %s", len(stage_tinctures), stage["name"])

    return TinctureProvider(stage_tinctures)
