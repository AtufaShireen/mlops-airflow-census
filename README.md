Mlops pipeline for consumer complaint dataset 
## How to setup airflow

Set airflow directory
```
export AIRFLOW_HOME="/home/atufa/census_consumer_project/census_consumer_complaint/airflow"
```

To install airflow 
```
pip install apache-airflow
```

To configure databse
```
airflow db init
```

To create login user for airflow
```
airflow users create  -e atufa@ineuron.ai -f atufa -l shireen -p admin -r Admin  -u admin
```
To start scheduler
```
airflow scheduler
```
To launch airflow server
```
airflow webserver -p <port_number>
```

```
pip install pandas-tfrecords
```

```
pip install \
  --upgrade --ignore-installed \
  python-snappy==0.5.1 \
  --global-option=build_ext \
  --global-option="-I/usr/local/include" \
  --global-option="-L/usr/local/lib"
```