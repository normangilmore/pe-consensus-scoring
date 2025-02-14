import numpy as np
import pandas as pd
from math import floor
import csv
import os
import argparse

from UnitizingScoring import toArray, scorePercentageUnitizing, getIndicesFromUser
from ThresholdMatrix import evalThresholdMatrix

STRICT_MINIMUM_CONTRIBUTORS = 1

path1 = 'SemanticsTriager1.3C2-2018-07-28T21.csv'
path2 = 'FormTriager1.2C2-2018-07-28T21.csv'
jpath1 = 'FormTriager1.2C2-2018-07-25T23.json'
jpath2 = 'SemanticsTriager1.3C2-2018-07-25T23.json'

def importData(path, out_path):
    '''

    :param path: location of the triage data
    :param out_path: where triage data should get output too. includes name of the ouptut file, should be a .csv
    :return:
    '''
    """CSV INPUT"""
    data = pd.read_csv(path, encoding = 'utf-8')
    #only excluding users for purpose of cleaner test data
    #Quang Gold--Duplicate Data from the real Quang
    #excludedUsers.append('40bbbf7e-a77b-498d-bb44-2ef6601061ef')
    article_shas = np.unique(data['article_sha256'])
    out = [['article_filename','article_sha256', 'source_task_uuid', 'namespace','start_pos', 'end_pos', 'topic_name', 'case_number', 'target_text']]
    for a in article_shas:
        art_data = data.loc[data['article_sha256'] == a]

        filename = art_data['article_filename'].tolist()
        users = art_data['contributor_uuid'].tolist()
        annotator_count = len(np.unique(users))
        flags = art_data['case_number'].tolist()
        cats = art_data['topic_name'].tolist()
        art_users = art_data['contributor_uuid'].tolist()
        #numUsers = len(np.unique(art_users))
        numUsers = art_data['taskrun_count'].iloc[0]
        #redundancy = art_data['']
        length = art_data['article_text_length'].iloc[0]
        #print(length)
        source_text = makeList(length)
        #flagExclusions = exclusionList(users, flags, cats)
        flagExclusions = []
        #print(flagExclusions)
        if annotator_count >= STRICT_MINIMUM_CONTRIBUTORS:
            cats = np.unique(art_data['topic_name'])
            for c in cats:
                cat_data = art_data.loc[art_data['topic_name'] == c]
                starts = [int(s) for s in cat_data['start_pos'].tolist()]
                ends = [int(e) for e in cat_data['end_pos'].tolist()]
                users = cat_data['contributor_uuid'].tolist()
                task_uuids = cat_data['highlight_task_uuid'].tolist()
                flags = cat_data['case_number'].tolist()
                namespaces = cat_data['namespace'].tolist()

                length = floor(cat_data['article_text_length'].tolist()[0])
                texts = cat_data['target_text'].str.decode('unicode-escape').tolist()

                print('//Article:', a, 'Category:', c, 'numUsers:', numUsers)
                source_text = addToSourceText(starts, ends, texts, source_text)
                pstarts, pends, pflags = scoreTriager(starts, ends, users, numUsers, flags, length, c, flagExclusions)
                out = appendData(filename[0], a, task_uuids, namespaces, pstarts, pends, c, pflags, out, source_text)

    scores = open(out_path, 'w', encoding = 'utf-8')

    with scores:
        writer = csv.writer(scores)
        writer.writerows(out)


def appendData(article_filename, article_sha256, task_uuids, namespaces,start_pos_list, end_pos_list, topic_name, case_numbers, data, source_text):
    if len(case_numbers) == 0:
        case_numbers = np.zeros(len(start_pos_list))
    for i in range(len(start_pos_list)):
        text = getText(start_pos_list[i], end_pos_list[i],source_text)
        text = text.encode('unicode-escape').decode('utf-8')
        #print(len(namespaces), len(start_pos_list), len(end_pos_list), len(case_numbers))
        data.append([article_filename, article_sha256, task_uuids[i], namespaces[i], start_pos_list[i], end_pos_list[i], topic_name, int(case_numbers[i]), text])
    return data
def getIndices(c, cats):
    indices = []
    for i in range(len(cats)):
        if cats[i] == c:
            indices.append(i)
    return indices
def scoreTriager(starts,ends, users, numUsers, inFlags, length, category, globalExclusion):
    #TODO: do this for each category
    #print('scoreT seu', len(starts), len(ends), len(users))
    passers = determinePassingIndices(starts, ends, numUsers, users, length, category)
    #print('glob', globalExclusion)
    #Bug: sometimes users aren't being excluded when they should, not a huge deal, happens one time in all the data
    #catExclusions = exclusionList(users, inFlags, minU = 6)
    #print('cat', catExclusions)
    #flagExclusions = np.unique(np.append(globalExclusion,catExclusions))
    #print('total exclusions', flagExclusions)
    #excl = findExcludedIndices(flagExclusions, users)
    #print(excl)
    #print('flagspreExcl', inFlags)
   # #/ if len(excl > 1):
   #      inFlags = exclude(excl, inFlags)
   #      users = exclude(excl, users)
   #      #ok to clip starts, ends because already know what passed
   #      starts, ends = exclude(excl,starts), exclude(excl, ends)
   #  #
    codetoUser, userToCode= codeNameDict(users)
    #print(codetoUser)
    coded = codeUsers(userToCode, users)
    #print(coded, numUsers)
    newStarts, newEnds = toStartsEnds(passers)
    flags = determineFlags(starts, ends, newStarts, newEnds, coded, inFlags)
    # print('Starts:',newStarts)
    # print('Ends:',newEnds)
    # print('Flags:', flags)
    # print('---------------------------')
    return newStarts, newEnds,flags

def findExcludedIndices(exclusions, users):
    #print(exclusions, users)
    indices = np.array(())
    for u in np.unique(users):
        if u in exclusions:
            uIndices = getIndicesFromUser(users, u)
            #print(uIndices)
            indices = np.append(indices,uIndices)
    #print('indices', indices)
    return indices
def exclude(indices, arr):
    # print(flags, len(flags))
    # print('indices',indices)
    arr = np.array(arr)
    return np.delete(arr, indices)
def exclusionList(users, flags,cats = None, minU= 8):
    excluded = []
    flags = np.array(flags)
    for u in np.unique(users):
        myUserIndices = getIndicesFromUser(users, u)
        # print(myUserIndices)
        # print(np.array(users)[myUserIndices])
        oneCount = 0
        pot = 0
        score = 0
        #print(myUserIndices)
        for i in myUserIndices:
            #print(i)
            if cats==None or cats[i]!= 'Language':
                if flags[i] == 1:
                    oneCount+=1
                pot = pot +1
        if pot>0:
            score = oneCount/pot
        if score>.8 and pot > minU:
            excluded.append(u)
    #print('excl', excluded,'users', np.unique(users))
    return excluded

def codeNameDict(users):
    uqUsers = np.sort(np.unique(users))
    codeDict = {}
    userDict = {}
    for i in range(len(uqUsers)):
        codeDict[i] = uqUsers[i]
        userDict[uqUsers[i]] = i
    return codeDict, userDict

def codeUsers(userDict, users):
    coded = []
    for u in users:
        coded.append(userDict[u])
    return coded
def determinePassingIndices(starts, ends, numUsers, users, length, category):
    #Defaults are evalThresholdmatrix, 1.4
    actionDeterminant = {
        'Language':
            {
                'passingFunc':evalThresholdMatrix,
                'scale':2.5
            },
        #hard to do, should be more lenient
        'Reasoning':
            {
                'passingFunc': evalThresholdMatrix,
                'scale': 2.5
            },
        #specialist can be stricter
        #be more clear
        'Evidence':
            {
                'passingFunc': minPercent,
                'scale': .35
            },
        'Probability':
            {
                'passingFunc': evalThresholdMatrix,
                'scale': 1.7
            },
        'Confidence':
            {
                'passingFunc': evalThresholdMatrix,
                'scale': 2.1
            },
        'Quoted Sources':
            {
                'passingFunc': evalThresholdMatrix,
                'scale': 1.6
            },
        #keepstrict
        'Needs Fact-Check':
            {
                'passingFunc': evalThresholdMatrix,
                'scale': 1.6
            },
        #wait formore training, see what happens
        'Arguments':
            {
                'passingFunc': evalThresholdMatrix,
                'scale': 2.5
            },
        'Assertions':
            {
                'passingFunc': evalThresholdMatrix,
                'scale': 1.8
            },
    }
    passFunc = actionDeterminant[category]['passingFunc']
    scale = actionDeterminant[category]['scale']

    return findPassingIndices(starts, ends, numUsers, users, length, passFunc , scale)

def findPassingIndices(starts, ends, numUsers, users, length, passingFunc = evalThresholdMatrix, scale = 1.4):
    """passingFunc must take in 3 arguments, first is a percentage, second is numberof users, 3rd is the scale
        what the scale is can very for different methods of evaluating passes/fails"""
    #print(starts)
    #print('findPI seu', len(starts), len(ends), len(users))
    answerMatrix = toArray(starts, ends, length, users)
    percentageArray = scorePercentageUnitizing(answerMatrix, length, numUsers)
    passersArray = np.zeros(len(percentageArray))
    # TODO: instead of passing to threshold matrix each time, just find out minScoretoPass
    for i in range(len(percentageArray)):
        if passingFunc(percentageArray[i], numUsers, scale) == 'H':
            passersArray[i] = 1
    return passersArray

def minPercent(percent, totalNumUsers, scale):
    if percent>=scale:
        return 'H'
    elif percent+.2>=scale:
        return 'M'
    else:
        return 'L'
def minNumUsers(percent, totalNumUsers, scale):
    """Scale is the minimum number of users required to call it a pass"""
    numInAgreement = percent*totalNumUsers
    if numInAgreement >= scale:
        return 'H'
    elif numInAgreement +2 >= scale:
        return 'M'
    else:
        return 'L'

def toStartsEnds(passers):
    prev = 0
    starts = []
    ends = []
    for i in range(len(passers)):
        if passers[i] != prev:
            if prev == 0:
                starts.append(i)
            elif prev == 1:
                ends.append(i-1)
            prev = 1-prev
    if len(ends)<len(starts):
        ends.append(passers[-1])
    return starts, ends
def toFlagMatrix(starts, ends, nStarts, nEnds, codedUsers, flags):

    #take out numpy
    numUsers = countUsers(codedUsers)
    if len(nStarts)>0 and numUsers>0:
        flagMatrix = [[0]*len(nStarts) for u in range(numUsers)]
        #i corresponds tot he code of a user

        for i in np.arange(len(starts)):
            #print('i',i, codedUsers[i])
            l = starts[i]
            k = ends[i]

            for j in np.arange(len(nStarts)):
                #print(j)
                o = nStarts[j]
                if (starts[i] <= nStarts[j] and ends[i] >= nStarts[j]) or \
                        (starts[i] <= nEnds[j] and ends[i] >= nEnds[j]):
                    u  = codedUsers[i]
                    flagMatrix[u][j]= flags[i]
        return flagMatrix
    return []
def countUsers(users):
    #time complexity here is horrendous, I think inputs should be small enough that it doens't matter
    uq = []
    for u in users:
        if u not in uq:
            uq.append(u)
    return len(uq)
def assignFlags(matrix):
    numUsers = len(matrix)
    numNStarts = len(matrix[0])
    currFlag = 1
    sortedNStarts = []
    flags = [0]*numNStarts
    #in this loop; i is the lowest confirmed instance of the caseflag; j iterates through rest of the
    #possible slots to see who else agreed
    for i in range(numNStarts):
        if i not in sortedNStarts:
            sortedNStarts.append(i)
            flags[i] = currFlag
            currFlag = currFlag + 1
            for j in range(i, numNStarts):
                if j not in sortedNStarts:
                    score = 0
                    potential = 0
                    for u in range(numUsers):
                        if matrix[u][i] != 0 and matrix[u][j] != 0 :
                            potential += 1
                            if matrix[u][i] == matrix[u][j]:
                              score += 1
                    if potential > 0 and score/potential >= .5:
                        flags[j] = flags[i]
                        sortedNStarts.append(j)
    return flags


def determineFlags(starts, ends, nStarts, nEnds, codedUsers, flags):
    # print()
    # print('flags',flags)
    # print('users',codedUsers)
    matrix = toFlagMatrix(starts, ends, nStarts,nEnds, codedUsers, flags)
    # print('nStarts', nStarts)
    # print('mat',matrix)

    if len(matrix)>0 and len(matrix[0])>0:
        outFlags = assignFlags(matrix)
       # print("OUTPUT\n",outFlags)
        return outFlags
    return []

def addToSourceText(starts, ends, texts, sourceText):
    for i in range(len(starts)):
        pointer = 0
        for c in range(starts[i], ends[i]):
            sourceText[c] = texts[i][pointer]
            pointer +=1
    return sourceText
def makeList(size):
    out = []
    for i in range(size):
        out.append(0)
    return out

def getText(start,end, sourceText):
    out = ''
    for i in range(int(start),int(end)):
        out = out+sourceText[i]
    return out


def load_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--input-file',
        help='CSV file with highlights to filter for agreement.'
             'and Schema .csv files.')
    parser.add_argument(
        '-o', '--output-file',
        help='Output file')
    return parser.parse_args()

if __name__ == '__main__':
    args = load_args()
    input_file = '../data/highlighter/ESTF_HardTriage-2021-05-14T0016-Highlighter.csv'
    if args.input_file:
        input_file = args.input_file
    dirname = os.path.dirname(input_file)
    basename = os.path.basename(input_file)
    output_file = os.path.join(dirname, 'T_IAA_' + basename)
    if args.output_file:
        output_file = args.output_file
    print("Input: {}".format(input_file))
    print("Output: {}".format(output_file))
    importData(input_file, output_file)
