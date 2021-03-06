# -*- coding: utf-8 -*-
"""EDA_+_Linear_Regression.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1TymkHYOg98T0-8iehq1LPxG_zGLECM5N
"""

from google.colab import drive
drive.mount('/content/drive')

import pandas as pd
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import pairwise
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Lasso
import seaborn as sns
import matplotlib.pyplot as plt

project_dir = '/content/drive/My Drive/MIE368 Project/'
dataset_raw = pd.read_csv(project_dir+'dataset_onehot_cat_big.csv')
#categories = pd.read_csv(project_dir+'business_category_info.csv',index_col='business_name')

dataset_raw.head()

"""# Basic Cleaning
0. Drop columns not used right now
1. Convert types to datetime
2. Pick well-reviewed users and places
3. filter non-food categories
"""

dataset_sub = dataset_raw.drop(["review_text","business_address","business_city","business_state","business_postal_code","business_is_open","user_name","business_id","review_id","user_yelping_since",'business_categories'],axis=1)
dataset_sub['review_date'] = pd.to_datetime(dataset_sub['review_date'])
#dataset_sub['user_yelping_since'] = pd.to_datetime(dataset_sub['user_yelping_since'])
dataset_sub.head()

dataset_sub.describe()

business_review_counts = dataset_raw["business_name"].value_counts()
popular_names = business_review_counts[business_review_counts>30].index
business_review_counts.to_csv(project_dir+"business_name_popularity.csv",index=False)
popular_names

categories.dropna(inplace=True)
TBRemoved = {'Beauty & Spas','Event Planning & Services','Hotels & Travel',
             'Arts & Entertainment','Shopping','Active Life','Fashion','Local Services',
             'Hair Removal','Transportation','Health & Medical','Public Services & Government',
             'Books',
             ' Mags',
              ' Music & Video',
              'Home & Garden',
              'Home Services',
              'Flowers & Gifts',
              'Arts & Crafts',
              'Professional Services',
              'Automotive',
              'Fitness & Instruction',
              'Museums',
              'Hair Salons',
              'Specialty Schools',
              'Photographers',
              'Pets',
             'Eyewear & Opticians',
             'Laundry Services',
             'Sporting Goods',
              'Tours'
             }
food_categories = set()
for cat in categories["parent_categories"]:
  if not pd.isna(cat):
    splitted = set(cat.split(','))
    if splitted & TBRemoved:
      continue
    food_categories.update(splitted)
food_business_names = set(categories[categories["parent_categories"].map(lambda c: bool(set(str(c).split(',')) & food_categories))].index)
food_categories

ACTIVE_USER_REVIEWS = 50
i_active = (dataset_sub['user_review_count']>=ACTIVE_USER_REVIEWS)
business_universe = popular_names & food_business_names
i_popular = dataset_sub['business_name'].map(lambda n:n in business_universe)
dataset_active = dataset_sub[i_active & i_popular]

i_active.mean(), i_popular.mean(), (i_active & i_popular).mean()

dataset_active.groupby("business_name").size().describe()

dataset_active.groupby("user_id").size().describe()

"""## Augmenting
1. Combine reaction columns
2. Add price and category info
3. Cluster categories to reduce dimensin
"""

review_reaction_cols = ['review_useful','review_funny','review_cool']
dataset_active['review_reactions'] = dataset_active[review_reaction_cols].sum(axis=1)

user_popularity_cols = ['user_useful','user_funny','user_cool','user_fans','user_compliment_hot','user_compliment_more','user_compliment_profile','user_compliment_cute','user_compliment_list','user_compliment_note','user_compliment_plain','user_compliment_cool','user_compliment_funny','user_compliment_writer','user_compliment_photos']
dataset_active['user_popularity'] = dataset_active[user_popularity_cols].sum(axis=1)

d = categories.to_dict()
dataset_active["categories"] = dataset_active["business_name"].map(lambda name: d['immediate_categories'][name])
dataset_active["price"] = dataset_active["business_name"].map(lambda name: d['price'][name].count('$'))

dataset_augmented = dataset_active.drop([*review_reaction_cols,*user_popularity_cols],axis=1)
dataset_augmented.describe()

unique_categories = dataset_augmented["categories"].unique()
vectorizer = CountVectorizer()
splitted_words = vectorizer.fit_transform(list(map(lambda w: ' '.join(c.replace(" ","").replace("(",'').replace(")",'').replace("&",'').replace("/",'') for c in w.split(', ')), unique_categories)))
feature_names = pd.DataFrame(splitted_words.toarray(),columns=vectorizer.get_feature_names(),index=unique_categories)
feature_names.head(10)

inertia = []
for k in range(3,33):
  print(k)
  hcluster = KMeans(n_clusters=k,n_init=20)
  hcluster.fit(feature_names)
  inertia.append(hcluster.inertia_)
pd.Series(inertia).plot.line()

categories_cluster = pd.DataFrame({'categories':unique_categories,'cluster':hcluster.labels_})

from collections import defaultdict, Counter
groups = defaultdict(Counter)
for i,row in categories_cluster.iterrows():
  groups[row['cluster']].update(row['categories'].split(', '))
for category, group in groups.items():
  print(group.most_common(3))

cat_to_cluster = {row['categories']:row['cluster'] for i,row in categories_cluster.iterrows()}
dataset_clustered = pd.concat([dataset_augmented,pd.get_dummies(dataset_augmented['categories'].map(cat_to_cluster.get),prefix='cluster_')],axis=1)

dataset_clustered[dataset_clustered['cluster__2'] == 1]['business_name'].value_counts()

"""# Baseline Model: Linear Regression"""

num_cols = dataset_raw.describe().columns
dataset = dataset_raw[num_cols].drop(['business_stars','user_average_stars'],axis=1)
dataset

dataset.describe()

def squeeze_01(df:pd.DataFrame):
  return (df-df.min())/(df.max()-df.min())
def log_transform(df:pd.DataFrame):
  return pd.DataFrame(np.log10(df+1),index=df.index,columns=df.columns)

squeeze_cols = ['business_latitude','business_longitude']
right_skewed_cols = ['business_review_count','user_review_count','review_popularity','user_popularity']
dataset[squeeze_cols] = squeeze_01(dataset[squeeze_cols])
dataset[right_skewed_cols] = log_transform(dataset[right_skewed_cols])

dataset.describe()

target= 'review_stars'
Y = dataset[target]
X = dataset.drop([target],axis=1)
X_train, X_test, y_train, y_test = train_test_split(X,Y,train_size=0.5,random_state=1)

def dependency_plot(X:pd.DataFrame,y:pd.Series):
  for col in X.columns:
    sns.scatterplot(x=X[col],y=y)
    plt.title(col)
    plt.show()
# dependency_plot(X_train,y_train)

model = Lasso(alpha=0.01)
model.fit(X_train,y_train)

model.score(X_train,y_train), model.score(X_test,y_test)

def round_star(n:float):
  if n > 5:
    return 5
  if n < 1:
    return 1
  return round(n)
y_pred = [round_star(y) for y in model.predict(X_train)]
y_pred_test = [round_star(y) for y in model.predict(X_test)]
(y_pred == y_train).mean(), (y_pred_test == y_test).mean()

pd.Series(model.coef_,index=X_train.columns).sort_values()