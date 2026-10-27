"""CloudWatch custom metrics (namespace VibraLens). No-op unless running with the AWS backend."""
import logging

from . import config

log = logging.getLogger("vibralens.metrics")
_cw = None


def put(name: str, value: float = 1.0, unit: str = "Count", **dims):
    if config.BACKEND != "aws":
        return
    global _cw
    try:
        if _cw is None:
            import boto3
            _cw = boto3.client("cloudwatch", region_name=config.AWS_REGION)
        _cw.put_metric_data(Namespace="VibraLens", MetricData=[{
            "MetricName": name, "Value": value, "Unit": unit,
            "Dimensions": [{"Name": k, "Value": str(v)} for k, v in dims.items()]}])
    except Exception as e:  # metrics must never break processing
        log.warning("metric %s not sent: %s", name, e)
