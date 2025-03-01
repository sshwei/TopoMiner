
from log import logger
from Save_ret import *
from yarrp import *
from genip import *
import time
from collections import defaultdict
from Common_profix import *
from Expension_prefix import *
import collections
from Save_ret import *
from tracert_ip import *
from Extract_prefix import *
from tqdm import tqdm
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor


NASip=set()#In order to store IP addresses that cannot be found with AS numbers
Discoveradd=set()#In order to store nodes with AS discovered
totalfrefixes=set()
ASes=set()
ComPre=set()#To store the common prefix of each discovered IP group



def process_item(item):
    global totalfrefixes
    # if item not in totalfrefixes and item is not None:
    if item is not None:
        ip = gip(item)
        if ip is not None:  
            return ip
        

def parallel_processing(chapres):
    Neip = []
    if len(chapres)>0:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            results = executor.map(process_item, chapres)
            for result in results:
                if result is not None:
                    Neip.append(result)
    return Neip 

def group_ip(final_ip_list):
    global Discoveradd #Number of discovered interface
    global NASip
    global ASes

    ases= defaultdict(list)
    tmpas=defaultdict(list)
    tmp_nasip=[]
    tmp_naip=set()
    tmp_aip=set()
    tmpadd=set()
   
    Dadd=set()
    Dadd=Discoveradd|NASip
    
    tmpadd=(Dadd|set(final_ip_list))-Dadd
    for ip in final_ip_list:
        as_number = get_asn(ip)
        if as_number and as_number!=23910: #23910 is Probe Local ASN
            if as_number not in ASes:
                ases[as_number].append(ip)
            else:
                tmpas[as_number].append(ip)               
        elif as_number is None and ip not in NASip:
            tmp_nasip.append(ip)
            tmp_naip.add(ip)
        for as_num, ip_list in tmpas.items():
            is_invalid = False
            for ip in ip_list:
                if ip not in Discoveradd:
                    is_invalid = True
                    break
            if is_invalid:
                ases[as_num]=ip_list
        tmp_aip=tmpadd-tmp_naip
    return ases,tmp_nasip,len(tmpadd),tmp_aip,tmp_naip

def deduplicate_list(lst):
    seen = set()
    result = []
    for item in lst:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result

def process_results(results):
    temp_dict= defaultdict(list)
    tmp_nasip = []
    ipnum = 0
    tmp_aip = set()
    tmp_naip = set()

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(group_ip, result) for result in results]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            for key, value in result[0].items():
                if key in temp_dict and set(temp_dict[key]) != set(value):
                    if isinstance(temp_dict[key], list):
                        temp_dict[key].extend(value)
                    else:
                        temp_dict[key] = [temp_dict[key], value]
                else:
                    temp_dict[key].extend(value)
            tmp_nasip.extend(result[1])
            ipnum += result[2]
            tmp_aip.update(result[3])
            tmp_naip.update(result[4])
    for key, value in temp_dict.items():
        temp_dict[key]= deduplicate_list(value)
    tmp_nasip=deduplicate_list(tmp_nasip)
    print(temp_dict)
    return temp_dict, tmp_nasip, ipnum, tmp_aip, tmp_naip

def collect_ip(ip_list):
    ip_lst=[]
    if len(ip_list)>1:
        for i in range(len(ip_list)-1):
            if ip_list[i][0]!=ip_list[i+1][0]:
                ip_lst.append(ip_list[i][0]) 
    ip_lst.append(ip_list[-1][0])
    return ip_lst


def get_New_ipdict(ip_lists,l):
    temp_dict=collections.OrderedDict()
    ipnum=0
    if len(ip_lists)>0:
        with ProcessPoolExecutor() as executor:
            results = executor.map(collect_ip, [iplist for iplist in ip_lists])
        temp_dict,tmp_nasip,ipnum,tmp_aip,tmp_naip=process_results(results)

        save_lenth_Disasadd(tmp_aip|tmp_naip,l)
        return temp_dict,tmp_nasip,ipnum,tmp_aip,tmp_naip


def topo_AS_Comprefix(temp_dict,tmp_nasip):
    global ComPre
    start_timec=time.time()
    pres=[]
    AS=set()
    if temp_dict:
        with ProcessPoolExecutor() as executor: 
            futures = []
            for as_num, ip_lst in temp_dict.items():
                future = executor.submit(extract_common_prefix, ip_lst)
                futures.append(future)
                AS.add(as_num)
            for future in concurrent.futures.as_completed(futures):
                pr = future.result()
                pres.extend(pr)
    preset=(ComPre|set(pres))-ComPre
    ComPre.update(preset)
    end_timec=time.time()
    elapsed_time=end_timec-start_timec
    logger.info(f"duration:{elapsed_time:.2f}s,Common prefix extraction complete.")
    return list(preset),AS


def clsass_prefixes(pfixes):
    if len(pfixes)>0:
        prefixes_by_length = {}
        for pfix in pfixes:
            if pfix is not None:
                prefix_length = int(pfix.split('/')[-1])
                if prefix_length in prefixes_by_length:
                    prefixes_by_length[prefix_length].append(pfix)
                else:
                    prefixes_by_length[prefix_length] = [pfix]
        return prefixes_by_length
    else:
        print("prefixes is none")
        return None
    

def total_comprefixes(targetpres):
    global packet
    global total_budget
    global lap
    global start_time
        
    totalcomps=[]
    Prx=[]
    add_no_prefix_class=[]
    Tmp_aip=set()
    Tmp_naip=set()
    Tmp_as=set()
    cround=0
    Len=0
    lenprefixes=0
    elapsed_time2=0.0

    prefixes_by_length=clsass_prefixes(targetpres) 
    logger.info(f"Prefixes are categorized")
    
    if prefixes_by_length:
        prelendict={}
        for length, prfs in prefixes_by_length.items():
            lenprefixes=len(prfs)
            Len=int(length)
            if (Len >= 32 and Len <=64) and lenprefixes >0:
                add_by_prefix_class=parallel_processing(prfs)   
                logger.info(f"Address generation is complete for this class prefix.")

                start_timef=time.time()
                if len(add_by_prefix_class)>0:
                    resultlist,p=trcacerout(add_by_prefix_class)
                    end_timef=time.time()
                    elapsed_time=end_timef-start_timef
                    logger.info(f"duration:{elapsed_time:.2f}s,This type of target address has been detected.")

                    cround+=1
                    packet+=p 
                    if packet >=total_budget:
                        lidict,linasip,tipnum,tmp_aip,tmp_naip=get_New_ipdict(resultlist,Len)
                        prelendict[Len]=int(round(tipnum/p * 100, 2))
                        if tipnum>0:
                            compres,AS=topo_AS_Comprefix(lidict,linasip)
                            totalcomps.extend(compres)
                            Tmp_aip.update(tmp_aip)
                            Tmp_naip.update(tmp_naip)
                            Tmp_as.update(AS)
                        break
                    if len(resultlist)>0:
                        
                        start_timee=time.time()
                        lidict,linasip,tipnum,tmp_aip,tmp_naip=get_New_ipdict(resultlist,Len)
                        end_timee=time.time()
                        elapsed_time=end_timee-start_timee
                        logger.info(f"duration:{elapsed_time:.2f}s,Separation of detection results complete.")

                        prelendict[Len]=int(round(tipnum/p * 100, 2))
                       
                        end_timef=time.time()
                        elapsed_time=end_timef-end_timee
                        logger.info(f"duration:{elapsed_time:.2f}s,Yield calculation completed.")


                        if tipnum>0:
                            compres,AS=topo_AS_Comprefix(lidict,linasip)
                            totalcomps.extend(compres)
                            end_timee=time.time()
                            elapsed_time=end_timee-end_timef
                            logger.info(f"duration:{elapsed_time:.2f}s,Common prefix extraction for this class of prefix probing results is complete.")

                            Tmp_aip.update(tmp_aip)
                            Tmp_naip.update(tmp_naip)
                            Tmp_as.update(AS)

                            end_timef=time.time()
                            elapsed_time2=end_timef-start_time

                            logger.info(f"round:{lap}.{cround} === Detection completed,Prefixes with length /{Len},New Discovered interface number:{tipnum},detecting rate of change to prefix:{round(tipnum/p * 100, 2)}% ")
                            logger.info(f"round:{lap}.{cround} === Addresses cumulative discovery:{len(Tmp_aip)+len(Tmp_naip)+len(Discoveradd|NASip)},ASes cumulative discovery:{len(Tmp_as|ASes)},packet cumulative sent:{packet},probing efficiency :{round((len(Tmp_aip)+len(Tmp_naip)+len(Discoveradd|NASip)) / packet * 100, 2)}% ,Duration of this detection:{elapsed_time2:.2f}s ")
                        else:
                            logger.info(f"round:{lap}.{cround} === Detection completed,Prefixes with length /{Len},New Discover interface number:{tipnum},Discover ases:0,Duration of this detection:{elapsed_time2:.2f}s ")
                            logger.info(f"round:{lap}.{cround} === Addresses cumulative discovery:{len(Tmp_aip)+len(Tmp_naip)+len(Discoveradd|NASip)},ASes cumulative discovery:{len(Tmp_as|ASes)},packet cumulative sent:{packet},probing efficiency :{round((len(Tmp_aip)+len(Tmp_naip)+len(Discoveradd|NASip)) / packet * 100, 2)}% ")
                    else:
                        logger.info(f"round:{lap}.{cround} === no route to the target,Prefixes with length /{Len}")
                        continue
            else:
                Prx.extend(prfs)
        if len(Prx)>0:
            
            start_timeg=time.time()

            add_no_prefix_class=parallel_processing(Prx)

            end_timeg=time.time()
            elapsed_time=end_timeg-start_timeg
            logger.info(f"duration:{elapsed_time:.2f}s,Address generation is complete for add_no_prefix_class.")

            resultlist,p=trcacerout(add_no_prefix_class)

            end_timeh=time.time()
            elapsed_time=end_timeh-end_timeg
            logger.info(f"duration:{elapsed_time:.2f}s,detection is complete for add_no_prefix_class.")
            
            end_time3=time.time()
            elapsed_time3=end_time3-start_time

            cround+=1
            le=0
            packet+=p 
            if len(resultlist)>0:
                NClidict,NClinasip,NCTip,NCtmp_aip,NCtmp_naip=get_New_ipdict(resultlist,le)

                end_timei=time.time()
                elapsed_time=end_timei-end_timeh
                logger.info(f"duration:{elapsed_time:.2f}s,Separation of detection results complete.")
                
                if NCTip>0:
                    compres,AS=topo_AS_Comprefix(NClidict,NClinasip)
                    totalcomps.extend(compres)
                    logger.info(f"round:{lap}.{cround} === Detection completed,Prefixes with length (length<32 and length>64 and number>100*g),New Discover interface number:{NCTip},Discover ases:{len(AS)},detecting rate of change to prefix:{round(tipnum/p * 100, 2)}% ,Duration of this detection:{elapsed_time3:.2f}s")
                    Tmp_aip.update(NCtmp_aip)
                    Tmp_naip.update(NCtmp_naip)
                    Tmp_as.update(AS)
                else:
                    logger.info(f"round:{lap}.{cround} ===  Detection completed,Prefixes with length (length<32 and length>64),Discover interface number:{NCTip},Discover ases:0,Duration of this detection:{elapsed_time3:.2f}s ")
                    logger.info(f"round:{lap}.{cround} === Addresses cumulative discovery:{len(Tmp_aip)+len(Tmp_naip)+len(Discoveradd|NASip)},ASes cumulative discovery:{len(Tmp_as|ASes)},packet cumulative sent:{packet},probing efficiency:{round((len(Tmp_aip)+len(Tmp_naip)+len(Discoveradd|NASip)) / packet * 100, 2)}% ")
            else:
                logger.info(f"round:{lap}.{cround} === no route to the target,Prefixes with (length<32 and length>64)")
        logger.info(f"round:{lap}=== Addresses cumulative discovery:{len(Tmp_aip)+len(Tmp_naip)+len(Discoveradd|NASip)},ASes cumulative discovery:{len(Tmp_as|ASes)},packet cumulative sent:{packet},probing efficiency:{round((len(Tmp_aip)+len(Tmp_naip)+len(Discoveradd|NASip)) / packet * 100, 2)}% ")
        logger.info(f"round:{lap}=== Detection completed")
        return list(set(totalcomps)),packet,prelendict,Tmp_aip,Tmp_naip,Tmp_as
    

def Calculate_coarse(prelendict,cor):
    cor=[64]
    values = prelendict.values() 
    threshold = sum(values) / len(values) 
    #threshold = int(0.02 * 100)  
    selected_keys = [key for key, value in prelendict.items() if value >= threshold]
    sorted_keys = sorted(selected_keys)
    cor.extend(sorted_keys)
    return cor


if __name__ == '__main__':
    start_time = time.time()
    logger.info("start_time:%s,Reading target prefixes",time.ctime(start_time))
    #Read target prefixes
    with open('data/testpre.txt', 'r') as file:#Enter the file of target prefix
        for line in file:
            prefix = line.strip()
            totalfrefixes.add(prefix)
            #read target address
    targetfile = "data/testadd.txt"# Enter the file of target address
    # bigbuket=len(totalfrefixes)
    HDAA=[] #high-density address area
    bigbuket=0 
    buketvol=0 
    cor=[64] 
    HDAA.extend(cor)
    total_budget=50000 #Setting the total number of packages to be sent
    Granularity=2 #Prefix expansion granularity
    packet=0
    lap=1

    logger.info(f"Total read target prefixes:{len(totalfrefixes)} ,general budget:{total_budget} ,Initial prefix expansion granularity:{Granularity},initial coares:{cor}")
    
    resultlist,p=first_detect(targetfile)

    end_timea=time.time()
    elapsed_time=end_timea-start_time
    logger.info(f"duration:{elapsed_time:.2f}s,first detection complete.")

    packet+=p
    lee=0 # the length of prefixes
    tmpd,tmpn,tmpm,tmpaip,tmpnaip=get_New_ipdict(resultlist,lee)

    end_timeb=time.time()
    elapsed_time=end_timeb-end_timea
    logger.info(f"duration:{elapsed_time:.2f}s,Processing of probing results complete.")

    Discoveradd.update(tmpaip)
    NASip.update(tmpnaip)
    
    end_timea=time.time()
    elapsed_time=end_timea-end_timeb
    logger.info(f"duration:{elapsed_time:.2f}s,Result saved complete.")
    tmpcopres,tmpas=topo_AS_Comprefix(tmpd,tmpn)
    ASes.update(tmpas)
    chanpres=chanpre(tmpcopres,Granularity,cor)
    
    end_timeb=time.time()
    elapsed_time=end_timeb-end_timea
    logger.info(f"duration:{elapsed_time:.2f}s,Prefix expansion complete.")

    end_time0=time.time()
    elapsed_time0=end_time0-start_time
    logger.info(f"round{lap} Detection completed,Prefix expansion granularity:{Granularity}, Duration of this detection:{elapsed_time0:.2f}s, Accumulated number of packet: {packet}, Accumulated interface addresses discovered this time: {len(Discoveradd | NASip)} The detection rate: {round(len(Discoveradd | NASip) / packet * 100,2)}%,Accumulated number of de-duplicate AS:{len(ASes)}")
    
    with tqdm(total_budget) as pbar:
        while True:
            old_pres=[]
            prelendict = {}
            totalcompres=[]

            buketvol=len(chanpres)
            if packet >=total_budget:
                break
            if buketvol>=bigbuket:
                bigbuket=buketvol

                totalfrefixes.update(set(chanpres))
                end_timea=time.time()
                elapsed_time=end_timea-end_timeb
                logger.info(f"duration:{elapsed_time:.2f}s,The number of prefixes generated is greater than the number of targets detected last round,number of prefixes generated:{bigbuket}")
            
            else:
                samplenum=bigbuket-buketvol
                old_pres=random_prefix(totalfrefixes,samplenum)
                totalfrefixes.update(set(chanpres))
                result_name='totalprefixes'
                save_result(result_name,totalfrefixes)
                
                end_timea=time.time()
                elapsed_time=end_timea-end_timeb
                logger.info(f"duration:{elapsed_time:.2f}s,The number of prefixes generated is less than the number of targets detected last round,Number of prefixes selected from the old prefix set:{len(old_pres)}")
               
                if len(old_pres)>0:
                    chanpres.extend(old_pres)
                else:
                    continue
            
            end_timeb=time.time()
            elapsed_time=end_timeb-end_timea
            logger.info(f"duration:{elapsed_time:.2f}s,Reading target prefixes complete,Number of prefixes:{len(chanpres)}")
           
            old_pres.clear()
            totalcompres,packet,prelendict,Tmp_aip,Tmp_naip,Tmp_as=total_comprefixes(chanpres)

            end_timea=time.time()
            elapsed_time=end_timea-end_timeb
            logger.info(f"duration:{elapsed_time:.2f}s,Common prefix extraction complete,Number of prefixes:{len(totalcompres)}")

            Discoveradd.update(Tmp_aip)
            NASip.update(Tmp_naip)
            ASes.update(Tmp_as)

            end_timeb=time.time()
            elapsed_time=end_timeb-end_timea
            logger.info(f"duration:{elapsed_time:.2f}s,Result saved complete.")
            
            end_time1= time.time()
            elapsed_time1=end_time1-start_time 
            logger.info(f"round:{lap} Detection completed, Duration of this detection:{elapsed_time1:.2f}s, Accumulated number of packet: {packet} Accumulated interface addresses discovered this time: {len(Discoveradd | NASip)},detection rate: {round(len(Discoveradd | NASip) / packet * 100,2)}%,Accumulated number of de-duplicate AS:{len(ASes)}")
           
            cor=Calculate_coarse(prelendict,cor)
            cor=list(set(cor))
            HDAA.extend(cor)
            cor.sort()

            Granularity=4
            logger.info(f"select coares:{cor}, granularity:{Granularity}") 
            chanpres=chanpre(totalcompres,Granularity,cor)

            end_timea=time.time()
            elapsed_time=end_timea-end_timeb
            logger.info(f"duration:{elapsed_time:.2f}s,Prefix expansion complete.")

            lap+=1
            elapsed_time1=''        
            pbar.update(packet)


    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info("star_time:%s,end_time:%s", time.ctime(start_time),time.ctime(end_time))
    result_name='Discoveradd' #Save those addresses where you can look up ASNs
    save_result(result_name,Discoveradd)
    result_name='No_ASN_ip' #Save those addresses without an ASN
    save_result(result_name,NASip)
    result_name='totalprefixes'#Save all prefixes
    save_result(result_name,totalfrefixes)
    Disadd=Discoveradd|NASip #Save all addresses
    result_name='Alldisadd'
    save_result(result_name,Disadd)
    print(HDAA)
    logger.info(f"Total detection time: {elapsed_time:.2f}s  total {lap} round Prefix expansion granularity:{Granularity}, Discovered total number of interface addresses: {len(Disadd)}, detection rate: {round(len(Discoveradd | NASip) / packet * 100,2)}%, Accumulated number of packet: {packet},Accumulated number of de-duplicate AS:{len(ASes)}")
    logger.info('all taskes completed')






