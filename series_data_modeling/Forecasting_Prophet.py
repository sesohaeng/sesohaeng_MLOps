import pandas as pd
import numpy as np
from prophet import Prophet
from datetime import datetime, timedelta
import holidays
import os
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import boto3
from matplotlib import rc, font_manager
# from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
import matplotlib as mpl
import io
import schedule
import time


# def job():
# S3 버킷 및 파일 경로
bucket_name = 'mlops-api-output'
file_key = '2023/2023.csv'

# S3 클라이언트 생성
s3 = boto3.client('s3', aws_access_key_id="{HIDDEN}", aws_secret_access_key="{HIDDEN}")

# CSV 파일 다운로드 및 읽기
response = s3.get_object(Bucket=bucket_name, Key=file_key)
df = pd.read_csv(io.BytesIO(response["Body"].read()))

df_index_list = df.index
df.insert(0,"지역",df_index_list)
df_reset= df.reset_index(drop=True)
df_reset['PPLTN_TIME']=df_reset['PPLTN_TIME'].apply(lambda _ : datetime.strptime(_,'%Y-%m-%d %H:%M'))
df_reset['PPLTN_TIME'] = df_reset['PPLTN_TIME'].dt.strftime('%Y-%m-%d %H:00:00')
local_list = df_reset["지역"].unique()


# 한국 휴일 객체 생성
kr_holidays = holidays.KR()
df_reset['holiday'] = df_reset.PPLTN_TIME.apply(lambda x: True if x in kr_holidays else False)
df = df_reset.rename(columns={'PPLTN_TIME': 'ds', 'AREA_PPLTN_MAX': 'y'})
df['ds'] = pd.to_datetime(df['ds'])


for i in local_list:

    plt.clf() # plt 초기화
    local_df = df["지역"] == "광화문·덕수궁"  # "지역" column에서 "경복궁" 값을 가지고 있는 행 추출
    print(i)
    filtered_local_df = df[local_df]


    # 날짜를 기준으로 정렬
    filtered_local_df = filtered_local_df.sort_values('ds', ascending=False)

    # 오늘 날짜 가져오기
    # latest_date = filtered_local_df.iloc[0]['ds']
    today = datetime.today().strftime("%Y-%m-%d 00:00:00")
    latest_date = datetime.today().strptime(today, "%Y-%m-%d 00:00:00")

    # 최근 n 일 동안의 데이터 선택
    start_date = latest_date - timedelta(days=30)

    new_df = filtered_local_df[filtered_local_df['ds'] >= start_date]

    test_day = latest_date
    new_df = new_df[new_df['ds'] <= test_day]

    # print(df['ds'])
    new_df = new_df.sort_values('ds', ascending=True)
    model = Prophet(
                #Trend
                growth="linear",
                changepoints=None,
                n_changepoints=10,
                changepoint_range=1,
                changepoint_prior_scale=0.5,
                interval_width=0.95,

                #Holiday
                holidays=None)
    model.fit(new_df)
    # 미래 예측 생성
    future = model.make_future_dataframe(freq="H",periods=24)
    # print(future)
    # 미래 예측
    forecast = model.predict(future)

    test_day = latest_date
    start_day = test_day - timedelta(days=1)

    test = new_df[new_df['ds'] > start_day]

    train = forecast[forecast['ds'] <= test_day]
    train = train[train['ds'] > start_day]
    # print(train)
    # print(train.info())

    predict = forecast[forecast['ds'] >= test_day]

    forecast = forecast[forecast['ds'] > start_day]



    # 관측된 데이터 포인트 제거
    # print(model.history.y)
    # future_predictions = forecast[df.shape[0]:]
    model.history.loc[:new_df.shape[0], 'y'] = None

    # 시각화
    fig = model.plot(forecast)
    ax = fig.gca()
    # x 축 눈금 설정
    locator = mdates.HourLocator(interval=2)  # 2시간 간격으로 눈금 설정
    formatter = mdates.DateFormatter('%m-%d %H')  # 날짜 형식 지정
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    plt.rcParams["font.family"] = 'NanumGothic' # 한글 폰트 적용
    mpl.rcParams['axes.unicode_minus'] = False
    # x축 눈금 설정
    plt.gca().spines['right'].set_visible(False)  # 오른쪽 테두리 제거
    #plt.gca().spines['top'].set_visible(False)  # 위 테두리 제거
    plt.gca().spines['left'].set_visible(False)  # 왼쪽 테두리 제거
    plt.gca().set_facecolor('#E6F0F8')  # 배경색

    # fcst_t = forecast['ds'].dt.to_pydatetime()
    # ax.plot(model.history['ds'].dt.to_pydatetime(), model.history['y'], color = 'black')
    ax.spines['left'].set_visible(False) # 왼쪽 여백 제거
    ax.spines['top'].set_visible(False) # 위쪽 여백 제거

    line0 = ax.fill_between(forecast['ds'], forecast['yhat_lower'], forecast['yhat_upper'], color='#edade4', alpha=0.3,label='bound') # 범주값 표시
    line1, = ax.plot(test['ds'], test['y'],color = 'black',label = 'Real data')
    line2, = ax.plot(predict['ds'], predict['yhat'], color='#8d2edb',label='Predict data') # 예측 값
    line3,= ax.plot(train['ds'], train['yhat'], color='#e64f3e', label='model data') # 실제값 추이

    # yticks = list(ax.get_yticks())  ## y축 눈금을 가져온다.
 #
    # for y in yticks:
    #     ax.axhline(y, linestyle=(0, (5, 2)), color='grey', alpha=0.5)  ## 눈금선 생성

    #plt.title("%s 인구혼잡도" % i, weight='bold',fontsize=10)
    plt.xlabel("날짜")
    plt.xticks(rotation=45, ha='right',weight='bold')
    plt.ylabel('인구혼잡도', rotation='vertical', ha='right',weight='bold')
    ax.legend(handles=[line0, line1, line2, line3], loc='upper left', fontsize=8,
          labels=['예측값범위', '실제 값', '예측 값','모델 결과값'], edgecolor='black', shadow=True)

    # plt.savefig("%s_model.png" % i,bbox_inches = 'tight') # 각 구에 맞는 나이 비율 이미지
    plt.show()
    #     plt.close()
    #
    #     output_filename = "%s_model.png" % i
    #     file_name = output_filename
    #
    #     file_path = os.path.realpath(output_filename)
    # # # # S3 버킷 이름과 업로드할 객체 키를 지정합니다.
    #     bucket_name = 'mlops-models-bucket'
    #     object_key = "prophet/" + "%s/" % i + file_name
    #     # 로컬 파일을 S3에 업로드합니다.
    #     s3.upload_file(file_path, bucket_name, object_key)
    # break
# schedule.every().day.at("00:05").do(job)
#
# while True:
#     schedule.run_pending()
#     time.sleep(1)
