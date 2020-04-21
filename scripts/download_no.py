import logging
import os
import re
from io import StringIO
import json
import ast

import dateutil
import pandas as pd
import requests
import lxml
from lxml import etree, html

from utils import (_COLUMNS_ORDER, COVIDScrapper, DailyAggregator,
                   DailyTransformation, retrieve_files)

logging.basicConfig()
logger = logging.getLogger("covid-eu-data.download.no")

# PDF Daily updates https://www.fhi.no/sv/smittsomme-sykdommer/corona/dags--og-ukerapporter/dags--og-ukerapporter-om-koronavirus/
REPORT_URL = "https://www.fhi.no/en/id/infectious-diseases/coronavirus/daily-reports/daily-reports-COVID19/"
DAILY_FOLDER = os.path.join("dataset", "daily", "no")
WEBPAGE_CACHE_FOLDER = os.path.join("documents", "daily", "no")

class SARSCOV2NO(COVIDScrapper):
    def __init__(self, url=None, daily_folder=None):
        if url is None:
            url = REPORT_URL

        if daily_folder is None:
            daily_folder = DAILY_FOLDER

        COVIDScrapper.__init__(self, url, country="NO", daily_folder=daily_folder)

    def extract_table(self):
        """Load data table from web page
        """

        re_data = re.compile(r"var data = (.*?);", re.MULTILINE)
        data = re_data.findall(self.req.text.replace('\n','').replace('\r', ''))

        if not len(data) == 2:
            raise Exception('only got one data table; should be two, one for cases one for rate')

        cases_data = ast.literal_eval(data[0])
        rate_data = ast.literal_eval(data[1])

        logger.info("Construct dataframe")
        cases_data = pd.DataFrame(cases_data, columns=["nuts_3", "cases"])
        rate_data = pd.DataFrame(rate_data, columns=["nuts_3", "cases/100k pop."])

        list_nuts_3 = {
            "no-no-18": "Nordland",
            "no-mr-15": "Møre og Romsdal",
            "no-tf-54": "Troms og Finnmark",
            "no-vt-38": "Vestfold og Telemark",
            "no-ag-42": "Agder",
            "no-ro-11": "Rogaland",
            "no-in-34": "Innlandet",
            "no-td-50": "Trøndelag",
            "no-vl-46": "Vestland",
            "no-vi-30": "Viken",
            "no-os-0301": "Oslo"
        }

        cases_data.replace(list_nuts_3, inplace=True)
        rate_data.replace(list_nuts_3, inplace=True)
        self.df = pd.merge(cases_data, rate_data, on="nuts_3")

        self.df["cases"] = self.df.cases.astype(int)

        logger.info("records cases:\n", self.df)

    def extract_datetime(self):
        """Get datetime of dataset
        Nombre de cas rapportés par région au 10/03/2020 à 15h (données Santé publique France)
        """
        re_dt = re.compile(r'<p><strong><span style="font-size: 1.1em;">Extract from daily COVID-19 report - (.*)</span></strong></p>')
        dt_from_re = re_dt.findall(self.req.text)

        if not dt_from_re:
            raise Exception("Did not find datetime from webpage")

        dt_from_re = dt_from_re[0]
        dt_from_re = dateutil.parser.parse(dt_from_re, dayfirst=True)
        self.dt = dt_from_re

    def post_processing(self):

        self.df.sort_values(by="cases", inplace=True)
        try:
            os.makedirs(WEBPAGE_CACHE_FOLDER)
        except FileExistsError as e:
            logger.info(f"{WEBPAGE_CACHE_FOLDER} already exists, no need to create folder")
            pass
        with open(
            os.path.join(WEBPAGE_CACHE_FOLDER, f"{self.dt.date().isoformat()}.html"),
            'wb'
        ) as f:
            f.write(self.req.content)




if __name__ == "__main__":
    # column_converter = {
    #     "county": "nuts_3"
    # }
    # drop_rows = {
    #     "county": "sum"
    # }

    # daily_files = retrieve_files(DAILY_FOLDER)
    # daily_files.sort()

    # for file in daily_files:
    #     file_path = os.path.join(DAILY_FOLDER, file)
    #     file_transformation = DailyTransformation(
    #         file_path=file_path,
    #         column_converter=column_converter,
    #         drop_rows=drop_rows
    #     )
    #     file_transformation.workflow()

    cov_no = SARSCOV2NO()
    cov_no.workflow()

    print(cov_no.df)

    da = DailyAggregator(
        base_folder="dataset",
        daily_folder=DAILY_FOLDER,
        country="NO"
    )
    da.workflow()

    print("End of Game")
