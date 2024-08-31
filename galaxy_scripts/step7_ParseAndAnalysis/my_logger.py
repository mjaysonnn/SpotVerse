# my_logger.py

import logging
import colorlog


class LoggerSetup:
    """
    Set up a logger with colorlog.
    """

    @staticmethod
    def setup_logger():
        """
        Set up a logger with colorlog
        :return:
        """
        log_format = (
            "%(asctime)s - "
            "%(levelname)-8s - "
            "%(filename)s:%(lineno)d - "
            "%(message)s"
        )

        colorlog_format = f"%(log_color)s{log_format}"

        colorlog.basicConfig(level=logging.DEBUG, format=colorlog_format, log_colors={
            'DEBUG': 'green',
            'INFO': 'blue',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        })

        return logging.getLogger()
