import streamlit as st
import pandas as pd
import numpy as np
import pickle  #to load a saved model
import base64  #to open .gif files in streamlit app
import h5py
import torch.utils.data as data_utils
from sklearn.preprocessing import LabelEncoder
import torch
from torch import nn
from torch import optim
import os 
from torch.autograd import Variable
from torch.utils.data import DataLoader
import torch.nn.functional as F
from annotated_text import annotated_text
import matplotlib.pyplot as plt
import seaborn as sns
from resource import getrusage, RUSAGE_SELF
from urllib.request import urlopen

#import pyreadr
st.title ("Methylation Based Tumor Classifier ")
#st.image("MHC_Digital_Treatments_Available_For_Blood_Cancer_Part_13_925x389pix_150322n_01_dc4d07f20e.jpg")
st.subheader("please using bed file containing header as [chrom chromStart chromEnd methylation_call probe_id] or bedMethyl without header but containing [CpG_chrm, CpG_beg, ]")
#st.video("S_example · Streamlit - Google Chrome 2022-12-19 15-28-09.mp4")


class NN_classifier(nn.Module):
    def __init__(self,n_input , n_output):
        super(NN_classifier, self).__init__()
        self.layer_out = nn.Linear(n_input, n_output, bias=False) 
    def forward(self, x):
        x = self.layer_out(x)
        return x  

### idebar


device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

#st.write(getrusage(RUSAGE_SELF).ru_maxrss)

#with st.sidebar:
st.write("Hello, you are running on ", device, 'device')
#option1 = st.radio('Pick A Trainningset:', ('Brain Tumor','Pan-cancer'))
option1 = st.radio('Pick a Trainingset', ['Pan-cancer_v5i','Brain Tumor'])

if option1 == 'Pan-cancer_v5i':
    model_files = pickle.load(urlopen("https://charitede-my.sharepoint.com/personal/dongsheng_yuan_charite_de/_layouts/52/download.aspx?share=EYHf66EDVJVPrjPaBimBcocBIGwCFvzx8MHOkrthOYj8CQ"))
elif option1 == 'Brain Tumor':
    model_files = pickle.load(urlopen("https://charitede-my.sharepoint.com/personal/dongsheng_yuan_charite_de/_layouts/52/download.aspx?share=Ef0MpN0rITNKmMJWET2MNJMBnoxgIEFe-3ktqM5YqTpEcQ"))
    
#with open(model_files_path,'rb') as f:
#    model_files = pickle.load(f)
anno_cpg = pickle.load(urlopen("https://charitede-my.sharepoint.com/personal/dongsheng_yuan_charite_de/_layouts/52/download.aspx?share=EYRxxhSOFjhLrbi30iEkKqYB6l3UVHbRGS3-NPTbAbv4ew"))

model = model_files[0]
enc =  model_files[1]
example_bed = model_files[2]
last_key = list(model)[-1]
DM = NN_classifier(model[last_key].size()[1],model[last_key].size()[0])
DM.load_state_dict(model)
DM.to(device)
print(DM)
def match_bs(anno_cpg,input_bed):
    res_bed = anno_cpg.merge(input_bed,how='left',on=["CpG_chrm", "CpG_beg"])
    res_bed = res_bed[~res_bed['beta_values'].isna()]
    input_bed = res_bed.filter(['CpG_chrm','CpG_beg','CpG_end_x','probe_strand','beta_values','Probe_ID'])
    input_bed = input_bed.rename(columns={'beta_values':'methylation_call','Probe_ID':'probe_id'})
    input_bed['methylation_call'] = np.where((input_bed.methylation_call < 60 ),-1,input_bed.methylation_call)
    input_bed['methylation_call'] = np.where((input_bed.methylation_call >= 60 ), 1,input_bed.methylation_call)
    input_dnn = example_bed.merge(input_bed,how='left')
    input_dnn['methylation_call']=input_dnn['methylation_call'].fillna(0)
    return input_dnn,len(input_bed)

option2 = st.selectbox('Types of Input Data',(['bed file','bedMethyl']))    

if option2 == 'bed file':
    uploaded_file = st.file_uploader('Upload a bed file as the example: ')
    if uploaded_file != None:
        st.success("File successfully uploaded")

        input_bed = pd.read_csv(uploaded_file,delim_whitespace=True)

        st.write(input_bed.head())
        input_bed['methylation_call'] = np.where((input_bed.methylation_call < 0.6 ),-1,input_bed.methylation_call)
        input_bed['methylation_call'] = np.where((input_bed.methylation_call > 0.6 ), 1,input_bed.methylation_call)
        input_cpgs = input_bed['probe_id'].tolist() 
        col1, col2 = st.columns(2)
        col1.metric(label="Number of Input CpG features", value=len(input_bed))
        col2.metric(label="Number of Features mapped to Trainingset", value=len(set(input_cpgs)&set(example_bed['probe_id'].tolist())))
        input_dnn = example_bed.merge(input_bed,how='left')
        input_dnn['methylation_call']=input_dnn['methylation_call'].fillna(0)
        torch_tensor = torch.tensor(input_dnn['methylation_call'].values)        

        DM.eval()
        with torch.no_grad():
            y_val_pred_masked = DM(torch_tensor.float().to(device))
            y_pred_softmax = torch.log_softmax(y_val_pred_masked,dim=0)
            _, y_pred_tags = torch.max(y_pred_softmax, dim = 0)
            label_pre = enc.inverse_transform([y_pred_tags.cpu()])
            proba = torch.max(torch.softmax( (y_val_pred_masked - y_val_pred_masked.mean().item())/y_val_pred_masked.std( unbiased=False).item(), dim = 0)).item()
            cs = torch.softmax( (y_val_pred_masked - y_val_pred_masked.mean().item())/y_val_pred_masked.std(unbiased=False).item(), dim = 0)
            #proba = torch.topk(cs, 1).values.tolist()

        annotated_text("The Prediction of our model is",   (f"{label_pre}","", "#ea9999") )
        annotated_text("The Confidence Score of the Prediction is",   (f"{proba}","", "#ea9999") )
        annotated_text("The Top5 Predictions")

        fig = plt.figure(figsize=(10, 4))
        df_bar = pd.DataFrame({'Confidence_Score':torch.topk(cs, 5).values.tolist(),'Tumor_Type':enc.inverse_transform(torch.topk(cs, 5).indices.tolist()).tolist()})
        sns.barplot(data=df_bar, x="Confidence_Score", y="Tumor_Type",orient='h')
        st.pyplot(fig)
    else:
        st.warning("please upload your file")
elif option2 == 'bedMethyl':
    uploaded_file = st.file_uploader('Upload a bed file as the example: ')
    if uploaded_file != None:
        st.success("File successfully uploaded")

        #input_bed = pd.read_csv(uploaded_file,delim_whitespace=True)
        input_bed = pd.read_csv(uploaded_file,delim_whitespace=True,header=None)
        input_bed.columns =['CpG_chrm','CpG_beg','CpG_end','Name','Score','Strandedness','start_codon','stop_codon','RGB','Coverage','beta_values']
        bedMethyl_sample,num_Features = match_bs(anno_cpg,input_bed)
        st.write(bedMethyl_sample.head())
        input_dnn = example_bed.merge(bedMethyl_sample,how='left')
        input_dnn['methylation_call']=input_dnn['methylation_call'].fillna(0)
        torch_tensor = torch.tensor(input_dnn['methylation_call'].values)   
        
        col1, col2 = st.columns(2)
        col1.metric(label="Number of Input features", value=len(input_bed))
        col2.metric(label="Number of Features mapped to Trainingset", value=num_Features)
       

        DM.eval()
        with torch.no_grad():
            y_val_pred_masked = DM(torch_tensor.float().to(device))
            y_pred_softmax = torch.log_softmax(y_val_pred_masked,dim=0)
            _, y_pred_tags = torch.max(y_pred_softmax, dim = 0)
            label_pre = enc.inverse_transform([y_pred_tags.cpu()])
            proba = torch.max(torch.softmax( (y_val_pred_masked - y_val_pred_masked.mean().item())/y_val_pred_masked.std( unbiased=False).item(), dim = 0)).item()
            cs = torch.softmax( (y_val_pred_masked - y_val_pred_masked.mean().item())/y_val_pred_masked.std(unbiased=False).item(), dim = 0)
            #proba = torch.topk(cs, 1).values.tolist()

        annotated_text("The Prediction of our model is",   (f"{label_pre}","", "#ea9999") )
        annotated_text("The Confidence Score of the Prediction is",   (f"{proba}","", "#ea9999") )
        annotated_text("The Top5 Predictions")

        fig = plt.figure(figsize=(10, 4))
        df_bar = pd.DataFrame({'Confidence_Score':torch.topk(cs, 5).values.tolist(),'Tumor_Type':enc.inverse_transform(torch.topk(cs, 5).indices.tolist()).tolist()})
        sns.barplot(data=df_bar, x="Confidence_Score", y="Tumor_Type",orient='h')
        st.pyplot(fig)
    else:
        st.warning("please upload your file")
