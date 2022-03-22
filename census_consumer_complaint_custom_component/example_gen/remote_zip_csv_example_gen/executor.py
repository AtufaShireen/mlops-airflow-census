# Copyright 2019 Google LLC. All Rights Reserved.
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
"""Remote Zip csv based TFX example gen executor."""
import datetime
import os
from typing import Any, Dict, Union
from tfx.dsl.io import fileio
from tfx.components.example_gen.csv_example_gen.executor import _CsvToExample
import pandas as pd
from absl import logging
import apache_beam as beam
import tensorflow as tf
from census_consumer_complaint_utils.utils import transform_csv_to_tf_record_file, download_datatset, extract_zip_file, \
    parse_file
from tfx.components.example_gen import utils
from tfx.components.example_gen.base_example_gen_executor import BaseExampleGenExecutor
from tfx.types import standard_component_specs
from census_consumer_complaint_types.types import REMOTE_ZIP_FILE_URI_KEY
from tfx.utils import io_utils
from tfx_bsl.coders import csv_decoder
import pandas as pd
from pandas_tfrecords.to_tfrecords import to_tfrecords
from pandas_tfrecords import pd2tf
from tfx.components.example_gen.import_example_gen.executor import _ImportSerializedRecord

from tfx.proto import example_gen_pb2


@beam.ptransform_fn
@beam.typehints.with_input_types(beam.Pipeline)
@beam.typehints.with_output_types(Union[tf.train.Example,
                                        tf.train.SequenceExample, bytes])
def ImportRecord(pipeline: beam.Pipeline, exec_properties: Dict[str, Any],
                 split_pattern: str) -> beam.pvalue.PCollection:
    """PTransform to import records.

  The records are tf.train.Example, tf.train.SequenceExample,
  or serialized proto.

  Args:
    pipeline: Beam pipeline.
    exec_properties: A dict of execution properties.
      - input_base: input dir that contains input data.
    split_pattern: Split.pattern in Input config, glob relative file pattern
      that maps to input files with root directory given by input_base.

  Returns:
    PCollection of records (tf.Example, tf.SequenceExample, or bytes).
  """
    output_payload_format = exec_properties.get(
        standard_component_specs.OUTPUT_DATA_FORMAT_KEY)

    serialized_records = (
            pipeline
            # pylint: disable=no-value-for-parameter
            | _ImportSerializedRecord(exec_properties, split_pattern))
    if output_payload_format == example_gen_pb2.PayloadFormat.FORMAT_PROTO:
        return serialized_records
    elif (output_payload_format ==
          example_gen_pb2.PayloadFormat.FORMAT_TF_EXAMPLE):
        return (serialized_records
                | 'ToTFExample' >> beam.Map(tf.train.Example.FromString))
    elif (output_payload_format ==
          example_gen_pb2.PayloadFormat.FORMAT_TF_SEQUENCE_EXAMPLE):
        return (serialized_records
                | 'ToTFSequenceExample' >> beam.Map(
                    tf.train.SequenceExample.FromString))

    raise ValueError('output_payload_format must be one of FORMAT_TF_EXAMPLE,'
                     ' FORMAT_TF_SEQUENCE_EXAMPLE or FORMAT_PROTO')


@beam.ptransform_fn
@beam.typehints.with_input_types(beam.Pipeline)
@beam.typehints.with_output_types(tf.train.Example)
def _ZipToExample(  # pylint: disable=invalid-name
        pipeline: beam.Pipeline, exec_properties: Dict[str, Any],
        split_pattern: str) -> beam.pvalue.PCollection:
    """Read remote zip csv files and transform to TF examples.

  Note that each input split will be transformed by this function separately.

  Args:
    pipeline: beam pipeline.
    exec_properties: A dict of execution properties.
      - input_base: input dir that contains Avro data.
    split_pattern: Split.pattern in Input config, glob relative file pattern
      that maps to input files with root directory given by input_base.

  Returns:
    PCollection of TF examples.
  """
    # directory to extract zip file

    input_base_uri = os.path.join(exec_properties[standard_component_specs.INPUT_BASE_KEY])

    # remote zip file uri to download zip file
    zip_file_uri = exec_properties[REMOTE_ZIP_FILE_URI_KEY]

    # downloading zip file from zip file uri into input_base_uri location
    zip_file_path = download_datatset(zip_file_uri, input_base_uri)
    extract_zip_file(zip_file_path, input_base_uri)
    os.remove(zip_file_path)

    for file in os.listdir(input_base_uri):
        csv_file_path = os.path.join(input_base_uri, file)
        df = pd.read_csv(csv_file_path, chunksize=200000)
        file_number = 1
        for data_set in df:
            data_set.dropna(inplace=True, subset=['Consumer disputed?'],axis=0)
            data_set['Consumer disputed?'] = data_set['Consumer disputed?'].replace({'Yes': 1.0, 'No': 0.0})
            data_set.to_csv(os.path.join(input_base_uri, f"file_{file_number}_{file}"), index=None, header=True)
            file_number += 1
            print(data_set.head())
            break
        os.remove(csv_file_path)

    # extracting zip file and deleteing zip file from directory

    # transform_csv_to_tf_record_file(csv_file_dir=input_base_uri, tf_record_file_dir=input_base_uri)
    # for file in os.listdir(input_base_uri):
    #     csv_file_path = os.path.join(input_base_uri,file)
    #     df=pd.read_csv(csv_file_path,low_memory=False)
    #     #to_tfrecords(df,input_base_uri,compression_type='GZIP', compression_level=9, columns=None,)
    #     df.dropna(inplace=True,axis=0)
    #     pd2tf(df,input_base_uri,compression_type='GZIP', compression_level=9, columns=None,)
    #     os.remove(csv_file_path)
    return _CsvToExample(exec_properties=exec_properties, split_pattern=split_pattern).expand(pipeline=pipeline)
    # return ImportRecord(pipeline=pipeline, exec_properties=exec_properties, split_pattern=split_pattern)


class Executor(BaseExampleGenExecutor):
    """TFX example gen executor for processing remote zip csv format.

  Data type conversion:
    integer types will be converted to tf.train.Feature with tf.train.Int64List.
    float types will be converted to tf.train.Feature with tf.train.FloatList.
    string types will be converted to tf.train.Feature with tf.train.BytesList
      and utf-8 encoding.

    Note that,
      Single value will be converted to a list of that single value.
      Missing value will be converted to empty tf.train.Feature().

    For details, check the dict_to_example function in example_gen.utils.


  Example usage:

    from tfx.components.base import executor_spec
    from tfx.components.example_gen.component import
    FileBasedExampleGen
    from tfx.components.example_gen.custom_executors import
    avro_executor

    example_gen = FileBasedExampleGen(
        input_base=avro_dir_path,
        custom_executor_spec=executor_spec.ExecutorClassSpec(
            avro_executor.Executor))
  """

    def GetInputSourceToExamplePTransform(self) -> beam.PTransform:
        """Returns PTransform for avro to TF examples."""
        return _ZipToExample
