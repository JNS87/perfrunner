import time
from typing import List, Tuple

from logger import logger
from perfrunner.helpers import local
from perfrunner.helpers.cbmonitor import timeit, with_stats
from perfrunner.helpers.worker import tpcds_initial_data_load_task
from perfrunner.tests import PerfTest
from perfrunner.tests.rebalance import RebalanceTest
from perfrunner.workloads.bigfun.driver import bigfun
from perfrunner.workloads.bigfun.query_gen import Query
from perfrunner.workloads.tpcdsfun.driver import tpcds


class BigFunTest(PerfTest):

    COLLECTORS = {'analytics': True}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.num_items = 0

    def create_datasets(self, bucket: str):
        self.disconnect_link()
        logger.info('Creating datasets')
        for dataset, key in (
            ('GleambookUsers', 'id'),
            ('GleambookMessages', 'message_id'),
            ('ChirpMessages', 'chirpid'),
        ):
            statement = "CREATE DATASET `{}` ON `{}` WHERE `{}` IS NOT UNKNOWN;"\
                .format(dataset, bucket, key)
            self.rest.exec_analytics_statement(self.analytics_nodes[0],
                                               statement)

    def create_index(self):
        logger.info('Creating indexes')
        for statement in (
            "CREATE INDEX usrSinceIdx   ON `GleambookUsers`(user_since: string);",
            "CREATE INDEX gbmSndTimeIdx ON `GleambookMessages`(send_time: string);",
            "CREATE INDEX cmSndTimeIdx  ON `ChirpMessages`(send_time: string);",
        ):
            self.rest.exec_analytics_statement(self.analytics_nodes[0],
                                               statement)

    def disconnect_bucket(self, bucket: str):
        logger.info('Disconnecting the bucket: {}'.format(bucket))
        statement = 'DISCONNECT BUCKET `{}`;'.format(bucket)
        self.rest.exec_analytics_statement(self.analytics_nodes[0],
                                           statement)

    def connect_buckets(self):
        logger.info('Connecting all buckets')
        statement = "CONNECT link Local"
        self.rest.exec_analytics_statement(self.analytics_nodes[0],
                                           statement)

    def disconnect_link(self):
        logger.info('DISCONNECT LINK Local')
        statement = "DISCONNECT LINK Local"
        self.rest.exec_analytics_statement(self.analytics_nodes[0],
                                           statement)

    def disconnect(self):
        for target in self.target_iterator:
            self.disconnect_bucket(target.bucket)

    def sync(self):
        for target in self.target_iterator:
            self.create_datasets(target.bucket)
            self.create_index()
        self.connect_buckets()
        for target in self.target_iterator:
            self.num_items += self.monitor.monitor_data_synced(target.node,
                                                               target.bucket)

    def re_sync(self):
        for target in self.target_iterator:
            self.connect_bucket(target.bucket)
            self.monitor.monitor_data_synced(target.node, target.bucket)

    def set_analytics_logging_level(self):
        log_level = self.test_config.analytics_settings.log_level
        self.rest.set_analytics_logging_level(self.analytics_nodes[0], log_level)
        self.rest.restart_analytics_cluster(self.analytics_nodes[0])
        if not self.rest.validate_analytics_logging_level(self.analytics_nodes[0], log_level):
            logger.error('Failed to set logging level {}'.format(log_level))

    def set_buffer_cache_page_size(self):
        page_size = self.test_config.analytics_settings.storage_buffer_cache_pagesize
        self.rest.set_analytics_page_size(self.analytics_nodes[0], page_size)
        self.rest.restart_analytics_cluster(self.analytics_nodes[0])

    def set_storage_compression_block(self):
        storage_compression_block = self.test_config.analytics_settings.storage_compression_block
        self.rest.set_analytics_storage_compression_block(self.analytics_nodes[0],
                                                          storage_compression_block)
        self.rest.restart_analytics_cluster(self.analytics_nodes[0])
        self.rest.validate_analytics_setting(self.analytics_nodes[0], 'storageCompressionBlock',
                                             storage_compression_block)

    def run(self):
        self.restore_local()
        self.wait_for_persistence()


class BigFunSyncTest(BigFunTest):

    def _report_kpi(self, sync_time: int):
        self.reporter.post(
            *self.metrics.avg_ingestion_rate(self.num_items, sync_time)
        )

    @with_stats
    @timeit
    def sync(self):
        super().sync()

    def run(self):
        super().run()

        sync_time = self.sync()

        self.report_kpi(sync_time)


class BigFunSyncWithCompressionTest(BigFunSyncTest):

    def run(self):
        self.set_storage_compression_block()
        super().run()


class BigFunSyncNoIndexTest(BigFunSyncTest):

    def create_index(self):
        pass


class BigFunIncrSyncTest(BigFunTest):

    def _report_kpi(self, sync_time: int):
        self.reporter.post(
            *self.metrics.avg_ingestion_rate(self.num_items, sync_time)
        )

    @with_stats
    @timeit
    def re_sync(self):
        super().re_sync()

    def run(self):
        super().run()

        self.sync()

        self.disconnect()

        super().run()

        sync_time = self.re_sync()

        self.report_kpi(sync_time)


class BigFunQueryTest(BigFunTest):

    QUERIES = 'perfrunner/workloads/bigfun/queries_with_index.json'

    def warmup(self) -> List[Tuple[Query, int]]:
        results = bigfun(self.rest,
                         nodes=self.analytics_nodes,
                         concurrency=self.test_config.access_settings.analytics_warmup_workers,
                         num_requests=int(self.test_config.access_settings.analytics_warmup_ops),
                         query_set=self.QUERIES)

        return [(query, latency) for query, latency in results]

    @with_stats
    def access(self, *args, **kwargs) -> List[Tuple[Query, int]]:
        results = bigfun(self.rest,
                         nodes=self.analytics_nodes,
                         concurrency=int(self.test_config.access_settings.workers),
                         num_requests=int(self.test_config.access_settings.ops),
                         query_set=self.QUERIES)
        return [(query, latency) for query, latency in results]

    def _report_kpi(self, results: List[Tuple[Query, int]]):
        for query, latency in results:
            self.reporter.post(
                *self.metrics.analytics_latency(query, latency)
            )

    def run(self):
        super().run()

        self.sync()

        logger.info('Running warmup phase')
        self.warmup()

        logger.info('Running access phase')
        results = self.access()

        self.report_kpi(results)


class BigFunQueryWithCompressionTest(BigFunQueryTest):

    def run(self):
        self.set_storage_compression_block()
        super().run()


class BigFunQueryNoIndexTest(BigFunQueryTest):

    QUERIES = 'perfrunner/workloads/bigfun/queries_without_index.json'

    def create_index(self):
        pass


class BigFunQueryNoIndexWithCompressionTest(BigFunQueryWithCompressionTest):

    QUERIES = 'perfrunner/workloads/bigfun/queries_without_index.json'

    def create_index(self):
        pass


class BigFunQueryNoIndexWindowFunctionsTest(BigFunQueryNoIndexTest):

    QUERIES = 'perfrunner/workloads/bigfun/queries_without_index_window_functions.json'


class BigFunRebalanceTest(BigFunTest, RebalanceTest):

    ALL_HOSTNAMES = True

    def rebalance_cbas(self):
        self.rebalance(services='cbas')

    def _report_kpi(self):
        self.reporter.post(
            *self.metrics.rebalance_time(rebalance_time=self.rebalance_time)
        )

    def run(self):
        super().run()

        self.sync()

        self.rebalance_cbas()

        if self.is_balanced():
            self.report_kpi()


class TPCDSTest(PerfTest):

    TPCDS_DATASETS = [
        "call_center",
        "catalog_page",
        "catalog_returns",
        "catalog_sales",
        "customer",
        "customer_address",
        "customer_demographics",
        "date_dim",
        "household_demographics",
        "income_band",
        "inventory",
        "item",
        "promotion",
        "reason",
        "ship_mode",
        "store",
        "store_returns",
        "store_sales",
        "time_dim",
        "warehouse",
        "web_page",
        "web_returns",
        "web_sales",
        "web_site",
    ]

    TPCDS_INDEXES = [("c_customer_sk_idx",
                      "customer(c_customer_sk:STRING)",
                      "customer"),
                     ("d_date_sk_idx",
                      "date_dim(d_date_sk:STRING)",
                      "date_dim"),
                     ("d_date_idx",
                      "date_dim(d_date:STRING)",
                      "date_dim"),
                     ("d_month_seq_idx",
                      "date_dim(d_month_seq:BIGINT)",
                      "date_dim"),
                     ("d_year_idx",
                      "date_dim(d_year:BIGINT)",
                      "date_dim"),
                     ("i_item_sk_idx",
                      "item(i_item_sk:STRING)",
                      "item"),
                     ("s_state_idx",
                      "store(s_state:STRING)",
                      "store"),
                     ("s_store_sk_idx",
                      "store(s_store_sk:STRING)",
                      "store"),
                     ("sr_returned_date_sk_idx",
                      "store_returns(sr_returned_date_sk:STRING)",
                      "store_returns"),
                     ("ss_sold_date_sk_idx",
                      "store_sales(ss_sold_date_sk:STRING)",
                      "store_sales")]

    COLLECTORS = {'analytics': True}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.num_items = 0

    def download_tpcds_couchbase_loader(self):
        if self.worker_manager.is_remote:
            self.remote.init_tpcds_couchbase_loader(
                repo=self.test_config.tpcds_loader_settings.repo,
                branch=self.test_config.tpcds_loader_settings.branch,
                worker_home=self.worker_manager.WORKER_HOME)
        else:
            local.init_tpcds_couchbase_loader(
                repo=self.test_config.tpcds_loader_settings.repo,
                branch=self.test_config.tpcds_loader_settings.branch)

    def set_max_active_writable_datasets(self):
        self.rest.set_analytics_max_active_writable_datasets(self.analytics_nodes[0], 24)
        self.rest.restart_analytics_cluster(self.analytics_nodes[0])
        self.rest.validate_analytics_setting(self.analytics_nodes[0],
                                             'storageMaxActiveWritableDatasets', 24)
        time.sleep(5)

    def load(self, *args, **kwargs):
        PerfTest.load(self, task=tpcds_initial_data_load_task)

    def create_datasets(self, bucket: str):
        logger.info('Creating datasets')
        for dataset in self.TPCDS_DATASETS:
            statement = "CREATE DATASET `{}` ON `{}` WHERE table_name = '{}';" \
                .format(dataset, bucket, dataset)
            logger.info('Running: {}'.format(statement))
            res = self.rest.exec_analytics_statement(
                self.analytics_nodes[0], statement)
            logger.info("Result: {}".format(str(res)))
            time.sleep(5)

    def create_indexes(self):
        logger.info('Creating indexes')
        for index in self.TPCDS_INDEXES:
            statement = "CREATE INDEX {} ON {};".format(index[0], index[1])
            logger.info('Running: {}'.format(statement))
            res = self.rest.exec_analytics_statement(
                self.analytics_nodes[0], statement)
            logger.info("Result: {}".format(str(res)))
            time.sleep(5)

    def drop_indexes(self):
        logger.info('Dropping indexes')
        for index in self.TPCDS_INDEXES:
            statement = "DROP INDEX {}.{};".format(index[2], index[0])
            logger.info('Running: {}'.format(statement))
            res = self.rest.exec_analytics_statement(
                self.analytics_nodes[0], statement)
            logger.info("Result: {}".format(str(res)))
            time.sleep(5)

    def connect_buckets(self):
        logger.info('Connecting all buckets')
        statement = "CONNECT link Local"
        logger.info('Running: {}'.format(statement))
        res = self.rest.exec_analytics_statement(
            self.analytics_nodes[0], statement)
        logger.info("Result: {}".format(str(res)))
        time.sleep(5)

    def create_primary_indexes(self):
        logger.info('Creating primary indexes')
        for dataset in self.TPCDS_DATASETS:
            statement = "CREATE PRIMARY INDEX ON {};".format(dataset)
            logger.info('Running: {}'.format(statement))
            res = self.rest.exec_analytics_statement(
                self.analytics_nodes[0], statement)
            logger.info("Result: {}".format(str(res)))
            time.sleep(5)

    def drop_primary_indexes(self):
        logger.info('Dropping primary indexes')
        for dataset in self.TPCDS_DATASETS:
            statement = "DROP INDEX {}.primary_idx_{};".format(dataset, dataset)
            logger.info('Running: {}'.format(statement))
            res = self.rest.exec_analytics_statement(
                self.analytics_nodes[0], statement)
            logger.info("Result: {}".format(str(res)))
            time.sleep(5)

    def sync(self):
        for target in self.target_iterator:
            self.create_datasets(target.bucket)
        self.connect_buckets()
        for target in self.target_iterator:
            self.num_items += self.monitor.monitor_data_synced(target.node,
                                                               target.bucket)

    def run(self):
        self.download_tpcds_couchbase_loader()
        self.set_max_active_writable_datasets()
        self.load()
        self.wait_for_persistence()
        self.compact_bucket()


class TPCDSQueryTest(TPCDSTest):

    COUNT_QUERIES = 'perfrunner/workloads/tpcdsfun/count_queries.json'
    QUERIES = 'perfrunner/workloads/tpcdsfun/queries.json'

    @with_stats
    def access(self, *args, **kwargs) -> (List[Tuple[Query, int]], List[Tuple[Query, int]]):

        logger.info('Running COUNT queries without primary key index')
        results = tpcds(self.rest,
                        nodes=self.analytics_nodes,
                        concurrency=self.test_config.access_settings.workers,
                        num_requests=int(self.test_config.access_settings.ops),
                        query_set=self.COUNT_QUERIES)
        count_without_index_results = [(query, latency) for query, latency in results]

        self.create_primary_indexes()

        logger.info('Running COUNT queries with primary key index')
        results = tpcds(self.rest,
                        nodes=self.analytics_nodes,
                        concurrency=self.test_config.access_settings.workers,
                        num_requests=int(self.test_config.access_settings.ops),
                        query_set=self.COUNT_QUERIES)
        count_with_index_results = [(query, latency) for query, latency in results]

        self.drop_primary_indexes()

        logger.info('Running queries without index')
        results = tpcds(
            self.rest,
            nodes=self.analytics_nodes,
            concurrency=self.test_config.access_settings.workers,
            num_requests=int(self.test_config.access_settings.ops),
            query_set=self.QUERIES)
        without_index_results = [(query, latency) for query, latency in results]

        self.create_indexes()

        logger.info('Running queries with index')
        results = tpcds(
            self.rest,
            nodes=self.analytics_nodes,
            concurrency=self.test_config.access_settings.workers,
            num_requests=int(self.test_config.access_settings.ops),
            query_set=self.QUERIES)
        with_index_results = [(query, latency) for query, latency in results]

        return \
            count_without_index_results, \
            count_with_index_results, \
            without_index_results, \
            with_index_results

    def _report_kpi(self, results: List[Tuple[Query, int]], with_index: bool):
        for query, latency in results:
            self.reporter.post(
                *self.metrics.analytics_volume_latency(query, latency, with_index)
            )

    def run(self):
        super().run()

        self.sync()

        count_results_no_index, count_results_with_index, results_no_index, \
            results_with_index = self.access()

        self.report_kpi(count_results_no_index, with_index=False)
        self.report_kpi(count_results_with_index, with_index=True)
        self.report_kpi(results_no_index, with_index=False)
        self.report_kpi(results_with_index, with_index=True)
