import sys

from census_consumer_complaint_component.data_ingestion import get_data_ingestion_components
from census_consumer_complaint_component.data_validation import get_data_validation_components
from census_consumer_complaint_component.data_preprocessing import get_data_preprocessing_components
from census_consumer_complaint_exception.exception import CensusConsumerException
from census_consumer_complaint_component.model_trainer import get_model_trainer_component
from census_consumer_complaint_component.model_evaluation import get_model_evaluation_component


def get_census_consumer_complaint_pipeline_component():
    try:

        pipeline_component = []

        # getting data ingestion component
        data_ingestion = get_data_ingestion_components()
        pipeline_component.append(data_ingestion.zip_example_gen)

        # getting data validation component
        data_validation = get_data_validation_components(data_ingestion=data_ingestion)
        pipeline_component.append(data_validation.statistic_gen)
        pipeline_component.append(data_validation.schema_gen)
        pipeline_component.append(data_validation.example_val)

        # getting data transformation component
        data_preprocessing = get_data_preprocessing_components(data_ingestion=data_ingestion,
                                                               data_validation=data_validation)

        pipeline_component.append(data_preprocessing.transformer)

        model_trainer = get_model_trainer_component(data_validation=data_validation,
                                                    data_preprocessing=data_preprocessing
                                                    )
        # returning pipeline component
        pipeline_component.append(model_trainer.trainer)

        # model_analysis = get_model_evaluation_component(data_ingestion=data_ingestion,
        #                                                 trainer=model_trainer)

        #pipeline_component.append(model_analysis.evaluator)
        return pipeline_component

    except Exception as e:
        raise (CensusConsumerException(e, sys)) from e
