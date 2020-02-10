# -*- coding: utf-8 -*-
"""Full_Model.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1MutZUIvKAwFFU0kVgDZ6z_tkgMOchcqC
"""

from google.colab import drive
drive.mount('/content/drive')

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import math
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import pairwise_distances
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
import gc
# from sklearn.cluster import KMeans, AgglomerativeClustering, AffinityPropagation
from sklearn.manifold import TSNE
# from sklearn.neighbors import VALID_METRICS, VALID_METRICS_SPARSE
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import confusion_matrix, mean_squared_error

def squeeze_01(df:pd.DataFrame):
  return (df-df.min())/(df.max()-df.min())
def log_transform(df:pd.DataFrame):
  return pd.DataFrame(np.log10(df),index=df.index,columns=df.columns)
def morethan(N:int):
  return lambda x:len(x)>N

project_dir = '/content/drive/My Drive/MIE368 Project/'
dataset_onehot_cat = pd.read_csv(project_dir+'dataset_onehot_cat.csv')
dataset_onehot_cat['user_yelping_since'] = pd.to_datetime(dataset_onehot_cat['user_yelping_since'],infer_datetime_format=True)
dataset_onehot_cat['review_date'] = pd.to_datetime(dataset_onehot_cat['review_date'],infer_datetime_format=True)
dataset_onehot_cat['days_before_review'] = pd.to_timedelta(dataset_onehot_cat['days_before_review']).map(lambda d:d.days)

dataset_active = dataset_onehot_cat.groupby("user_id").filter(morethan(50))
dataset = dataset_active
dataset_active.shape[0]/dataset_onehot_cat.shape[0]

"""# Content based
1. Similarity by category
2. Similarity by review text words mentioned
"""

def process_text(text):
  return ' '.join([t for t in text.replace('\n',' ').replace('_',' ').split(' ') if len(t)>2 and not any(c.isdigit() for c in t)])
def produce_counts(texts):
  gc.collect()
  counter = TfidfVectorizer(strip_accents='ascii',stop_words='english',sublinear_tf=True,max_df=0.8)
  counted = counter.fit_transform([process_text(t) for t in texts])
  vocab_s = pd.Series(counter.get_feature_names())
  gc.collect()
  return pd.DataFrame(counted.toarray(),index=texts.index,columns=vocab_s)
def get_top_N(counts_df:pd.DataFrame,N:int):
  return counts_df.apply(lambda counts: ' '.join(counts.sort_values()[-N:].index),axis=1)

by_business = dataset.groupby('business_name')['review_text'].apply(' '.join)
bus_review_word_freq = produce_counts(by_business)
bus_tops = get_top_N(bus_review_word_freq,10)

from itertools import islice
print("Business Frequent Words")
for k,v in islice(bus_tops.items(),10):
  print(k)
  print(v,end="\n\n")

vectorizer=CountVectorizer()
X=vectorizer.fit_transform(bus_tops)
count_df = pd.DataFrame(X.toarray(), index=bus_tops.index, columns=[n+"_mentioned" for n in vectorizer.get_feature_names()])
ifirst_cat_col = dataset.columns.to_list().index("price") + 1
cat_cols = dataset.columns[ifirst_cat_col:]
dataset_businesses = dataset.groupby("business_name")[cat_cols].first()
business_vectors = pd.concat([dataset_businesses,count_df],axis=1)
business_vectors

TSNER = TSNE(metric='cosine')
embedded = TSNER.fit_transform(business_vectors)
sns.scatterplot(x=embedded[:,0], y=embedded[:,1])

similarities = cosine_similarity(business_vectors,business_vectors)
for i in range(similarities.shape[0]):
  similarities[i,i] = 0
similarities_df = pd.DataFrame(similarities,index=business_vectors.index,columns=business_vectors.index)
similarities_df

def get_candidates(business_reviewed,N=10):
  row = similarities_df[business_reviewed].sort_values()[-N:]
  return row
get_candidates('Wow Sushi')

"""# Collaborative filtering"""

grouped = dataset.groupby(["user_id","business_name"])['review_stars'].last()
rating_matrix_raw = pd.DataFrame(grouped).reset_index().pivot(index="user_id",columns="business_name",values="review_stars")

# df_norm_T is transposed normalized df
rating_matrix_rawT = rating_matrix_raw.T
user_mean_ratings = rating_matrix_rawT.mean()
user_std_ratings = rating_matrix_rawT.std(ddof=0)
rating_matrix_normT = (rating_matrix_rawT - user_mean_ratings)/user_std_ratings

# df_norm is normalized df
rating_matrix_norm = rating_matrix_normT.T
# make sure we did not lose any rating during normalization
pd.isna(rating_matrix_norm).sum().sum(),pd.isna(rating_matrix_raw).sum().sum()

def predict_rating(user:str,place:str):
  existing_rating = rating_matrix_norm.loc[user,place]
  rating_matrix_norm.loc[user,place] = np.nan
  row = rating_matrix_norm.loc[user,:]
  similarities = (row * rating_matrix_norm).T.sum()
  similarities[user] = np.nan
  sim_sum = similarities.sum()
  rating = user_mean_ratings[user] + user_std_ratings[user]*(rating_matrix_norm.loc[:,place] * similarities).sum()/sim_sum
  rating_matrix_norm.loc[user,place] = existing_rating
  return rating

"""# Testing"""

raw_predictions = rating_matrix_norm+np.nan
rating_matrix_normT = rating_matrix_norm.T
for user, row in rating_matrix_norm.iterrows():
  similarities = (row * rating_matrix_norm).T.sum()
  # ignore the user's similarity with itself
  similarities[user] = np.nan
  sim_sum = similarities.sum()
  raw_predictions.loc[user,:]=user_mean_ratings[user] + user_std_ratings[user]*(similarities * rating_matrix_normT).T.sum()/sim_sum

predictions = np.round(raw_predictions)
flat_ratings = pd.Series(rating_matrix_raw.to_numpy().reshape(-1)).dropna()
comparable_predictions = predictions[~pd.isna(rating_matrix_raw)]
flat_raw_predictions = pd.Series(raw_predictions[~pd.isna(rating_matrix_raw)].to_numpy().reshape(-1)).dropna()
flat_predictions = pd.Series(comparable_predictions.to_numpy().reshape(-1)).dropna()
flat_ratings.shape,flat_predictions.shape

# Collaborative filtering accuracy
(flat_ratings==flat_predictions).mean()

(np.abs(flat_raw_predictions-flat_ratings)<=1).mean()

mean_squared_error(flat_ratings,flat_raw_predictions)

confusion = confusion_matrix(flat_ratings,flat_predictions,labels=[1,2,3,4,5])
confusion_df = pd.DataFrame(np.log(confusion+1),index=range(1,6),columns=range(1,6))
confusion_df.index.name="Predicted"
confusion_df.columns.name="Actual"
fig, ax = plt.subplots()
# sns.set(font_scale=1)#for label size
sns.heatmap(confusion_df, annot=True)# font size
ax.set_ylim(5, 0)
plt.title("Collaborative Filtering Confusion Matrix (Log scale)")

def extract_cat_accuracy(cat:str):
  reviews = dataset[dataset[cat]==1]
  actual = reviews['review_stars']
  predicted = [predictions.loc[row['user_id'],row['business_name']] for _, row in reviews.iterrows()]
  return [(actual == predicted).mean(), len(reviews)]
accuracies = {}
for cat in cat_cols:
  accuracies[cat] = extract_cat_accuracy(cat)

cat_accuracies = pd.DataFrame(accuracies).T
cat_accuracies.columns = ["Accuracy",'# reviews']
sns.scatterplot(data=cat_accuracies*100,x='# reviews',y='Accuracy')
plt.title("Accuracy per food category")
plt.ylim(0,100)

cat_accuracies[cat_accuracies['# reviews']>500].sort_values('Accuracy')

dataset['prediction'] = [predictions.loc[user_id,business_name] for user_id,business_name in zip(dataset['user_id'],dataset['business_name'])]

dataset['accuracy']=(dataset['prediction']==dataset['review_stars']).astype(int)
business_reviewedness = dataset.groupby("business_name")['business_review_count'].first()
business_accuracy = dataset.groupby("business_name")['accuracy'].mean()
sns.scatterplot(x=business_reviewedness,y=business_accuracy*100)
plt.title("Prediction accuracy vs # reviews per business")

dataset[dataset['business_review_count']>600].groupby("business_name")['accuracy'].mean().sort_values()

pd.isna(rating_matrix_raw).mean(axis=1).sort_values()

user = 'YsQeSdrgdme-Yug2hr1HUw'
places_been_to = rating_matrix_raw.loc[user,:]
places_been_to = places_been_to[~pd.isna(places_been_to)]

places_been_to

places_been_to = ['Pai Northern Thai Kitchen','Ruby Watchco','Mengrai Thai']
candidates = set()
for place in places_been_to:
  candidates.update(get_candidates(place,3).index)
print('\n'.join(candidates))

candidates_l = list(candidates)
ratings = pd.Series([predict_rating(user,can) for can in candidates_l],index=candidates_l).sort_values()[::-1]
ratings

rating_matrix_raw.iloc[::5,24:30]

