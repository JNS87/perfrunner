from logger import logger
from perfrunner.helpers.misc import pretty_dict, read_json
from perfrunner.tests import PerfTest
from perfrunner.tests.kv import ReadLatencyDGMTest, ThroughputDGMCompactedTest


class MagmaBenchmarkTest(PerfTest):

    def __init__(self, *args):
        super().__init__(*args)

        self.settings = self.test_config.magma_benchmark_settings
        self.stats_file = "stats.json"

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tear_down()

        if exc_type == KeyboardInterrupt:
            logger.warn('The test was interrupted')
            return True

    def create_command(self, write_multiplier: int = 1):

        cmd = "ulimit -n 1000000;/opt/couchbase/bin/magma_bench {DATA_DIR}/{ENGINE} " \
              "--kvstore {NUM_KVSTORES} --ndocs {NUM_DOCS} " \
              "--batch-size {WRITE_BATCHSIZE} --keylen {KEY_LEN} --vallen {DOC_SIZE} " \
              "--nwrites {NUM_WRITES} --nreads {NUM_READS} --nreaders {NUM_READERS} " \
              "--wcache-size {WRITECACHE_SIZE} --fs-cache-size {FS_CACHE_SIZE} " \
              "--engine {ENGINE} --engine-config {ENGINE_CONFIG} --stats {STATS_FILE}"\
            .format(NUM_KVSTORES=self.settings.num_kvstores, NUM_DOCS=self.settings.num_docs,
                    WRITE_BATCHSIZE=self.settings.write_batchsize, KEY_LEN=self.settings.key_len,
                    DOC_SIZE=self.settings.doc_size,
                    NUM_WRITES=(self.settings.num_writes * write_multiplier),
                    NUM_READS=self.settings.num_reads, NUM_READERS=self.settings.num_readers,
                    WRITECACHE_SIZE=self.settings.writecache_size,
                    FS_CACHE_SIZE=self.settings.fs_cache_size, DATA_DIR=self.settings.data_dir,
                    ENGINE=self.settings.engine, ENGINE_CONFIG=self.settings.engine_config,
                    STATS_FILE=self.stats_file)
        return cmd

    def run_and_get_stats(self, cmd: str) -> dict:
        self.remote.run_magma_benchmark(cmd, self.stats_file)
        data = read_json(self.stats_file)
        logger.info("\nStats: {}".format(pretty_dict(data)))
        return data

    def create(self):
        cmd = self.create_command()
        cmd += " --benchmark writeSequential --clear-existing"
        stats = self.run_and_get_stats(cmd)
        return stats["writer"]["Throughput"], stats["WriteAmp"], stats["SpaceAmp"]

    def read(self):
        cmd = self.create_command()
        cmd += " --benchmark readRandom"
        stats = self.run_and_get_stats(cmd)
        return stats["reader"]["Throughput"], stats["ReadIOAmp"], stats["BytesPerRead"]

    def update(self):
        cmd = self.create_command(write_multiplier=self.settings.write_multiplier)
        cmd += " --benchmark writeRandom"
        stats = self.run_and_get_stats(cmd)
        return stats["writer"]["Throughput"], stats["WriteAmp"], stats["SpaceAmp"]

    def _report_kpi(self, create_metrics, read_metrics, write_metrics):
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=create_metrics[0],
                                                  precision=0,
                                                  benchmark="Throughput, Write sequential")
        )
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=create_metrics[1],
                                                  precision=2,
                                                  benchmark="Write amplification, "
                                                            "Write sequential")
        )
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=create_metrics[2],
                                                  precision=2,
                                                  benchmark="Space amplification, "
                                                            "Write sequential")
        )
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=read_metrics[0],
                                                  precision=0,
                                                  benchmark="Throughput, Read random")
        )
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=read_metrics[1],
                                                  precision=2,
                                                  benchmark="Read IO amplification, Read random")
        )
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=read_metrics[2],
                                                  precision=1,
                                                  benchmark="Bytes per read, Read random")
        )
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=write_metrics[0],
                                                  precision=0,
                                                  benchmark="Throughput, Write random")
        )
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=write_metrics[1],
                                                  precision=2,
                                                  benchmark="Write amplification, Write random")
        )
        self.reporter.post(
            *self.metrics.magma_benchmark_metrics(throughput=write_metrics[2],
                                                  precision=2,
                                                  benchmark="Space amplification, Write random")
        )

    def run(self):
        self.remote.stop_server()

        create_metrics = self.create()

        read_metrics = self.read()

        write_metrics = self.update()

        self.report_kpi(create_metrics, read_metrics, write_metrics)


class ReadLatencyDGMMagmaTest(ReadLatencyDGMTest):

    COLLECTORS = {'disk': True, 'latency': True, 'net': False, 'kvstore': True}

    def __init__(self, *args):
        super().__init__(*args)

        self.collect_per_server_stats = self.test_config.magma_settings.collect_per_server_stats


class MixedLatencyDGMTest(ReadLatencyDGMMagmaTest):

    def _report_kpi(self):
        for operation in ('get', 'set'):
            self.reporter.post(
                *self.metrics.kv_latency(operation=operation)
            )


class ThroughputDGMCompactedMagmaTest(ThroughputDGMCompactedTest):

    COLLECTORS = {'disk': True, 'latency': True, 'net': False, 'kvstore': True}

    def __init__(self, *args):
        super().__init__(*args)

        self.collect_per_server_stats = self.test_config.magma_settings.collect_per_server_stats