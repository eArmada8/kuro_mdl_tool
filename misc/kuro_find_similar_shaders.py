# Kuro shader finder.  Give the filename of a shader e.g. 'chr_cloth#a8b9eb0baf9ad2dc'
# and it will search the database (by default 'kuro_shaders.csv', set below) to generate a report
# of the other switches, ranked by similarity.  Requires Python 3.10 or newer.
#
# Requires kuro_shaders.csv, obtain from
# https://raw.githubusercontent.com/eArmada8/kuro_mdl_tool/master/misc/kuro_shaders.csv
#
# GitHub eArmada8/kuro_mdl_tool

import os, csv

csv_file = 'kuro_shaders.csv'

class Shader_db:
    def __init__(self, shader_db_csv, report_file = 'report.txt'):
        self.shader_db_csv = shader_db_csv
        self.report_file = report_file
        self.shader_array = self.read_shader_csv()
        self.shader_switches = self.shader_array[0][3:]
        self.shader_sig = {x[0]:x[3:] for x in self.shader_array[1:]}
        self.diffs = {}
        self.restriction = ''
        self.restriction_column = None
        self.restricted_list = [x[0] for x in self.shader_array[1:]]
        self.report = ''

    def read_shader_csv (self):
        with open(self.shader_db_csv) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            return([row for row in csv_reader])

    def set_restricted_list (self, restriction):
        if restriction in self.shader_array[0][1:3]:
            self.restriction = restriction
            self.restriction_column = self.shader_array[0].index(restriction)
            self.restricted_list = [x[0] for x in self.shader_array[1:] if x[self.restriction_column] != '']
        else:
            self.restriction_column = None
            self.restricted_list = [x[0] for x in self.shader_array[1:]]
        return

    def diff(self, shader1, shader2): #Returns the value of shader2
        string1 = self.shader_sig[shader1]
        string2 = self.shader_sig[shader2]
        differences = [i for i in range(len(string1)) if string1[i] != string2[i]]
        return({self.shader_switches[i]:string2[i] for i in differences})

    def sort_shaders_by_similarity(self, shader, restrict_type = True):
        if restrict_type == True:
            shader_type = shader.split("#")[0]
            shader_sigs = {k:self.shader_sig[k] for k in self.shader_sig if k.split("#")[0] == shader_type}
        else:
            shader_sigs = self.shader_sig
        shader_diff = {k:sum([1 if shader_sigs[k][i] != shader_sigs[shader][i] else 0
            for i in range(len(shader_sigs[k]))]) for k in shader_sigs if k != shader}
        diff_val = sorted(list(set(shader_diff.values())))
        self.diffs = {diff_val[i]:{x:self.diff(shader,x) for x in shader_diff if shader_diff[x] == diff_val[i]}\
            for i in range(len(diff_val))}
        self.report = 'Original Shader: {0}\n'.format(shader)
        if self.restriction != '':
            self.report += '\nRestriction: {} is not None\n'.format(self.restriction)
        array_first_column = [x[0] for x in self.shader_array]
        for i in self.diffs:
            if len([j for j in self.diffs[i] if j in self.restricted_list]) > 0:
                self.report += '\nShaders with {} differences:\n\n'.format(i)
                for j in self.diffs[i]:
                    if j in self.restricted_list:
                        self.report += '{}:'.format(j)
                        if self.restriction_column != None:
                            row = array_first_column.index(j)
                            self.report += ' (available in {})\n'.format(self.shader_array[row][self.restriction_column])
                        else:
                            self.report += '\n'
                        self.report += '\n'.join(['{0}: {1}'.format(k,v) for (k,v)\
                            in self.diffs[i][j].items()]) + '\n\n'
        return(self.report)

    def generate_report(self, shader, restrict_type = True):
        with open(self.report_file,'w') as f:
            f.write(self.sort_shaders_by_similarity(shader, restrict_type = restrict_type))
        return

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    if os.path.exists(csv_file):
        shader_db = Shader_db(csv_file)
        shader = input("Please enter name of shader to analyze: ")
        while not shader in shader_db.shader_sig.keys():
            partial_matches = [x for x in shader_db.shader_sig.keys() if shader.lower() in x]
            if len(partial_matches) > 0: # We will only take the first
                confirm = input("{0} not found, did you mean {1}? (y/N) ".format(shader, partial_matches[0]))
                if confirm.lower() == 'y':
                    shader = partial_matches[0]
                else:
                    shader = input("Please enter name of shader to analyze: ")
            else:
                shader = input("Invalid entry. Please enter name of shader to analyze: ")
        restriction = input("Please enter game restriction [{}, or blank for None]: ".format(', '.join(shader_db.shader_array[0][1:3])))
        while not restriction in ['']+shader_db.shader_array[0][1:3]:
            restriction = input("Invalid entry. Please enter game restriction [{}, or blank for None]: ".format(', '.join(shader_db.shader_array[0][1:3])))
        restrict_type = True
        restrict_type_raw = input("Restrict matches to {}? [Y/n]: ".format(shader.split("#")[0]))
        if len(restrict_type_raw) > 0 and (str(restrict_type_raw).lower()[0]) == 'n':
            restrict_type = False
        shader_db.set_restricted_list(restriction)
        shader_db.report_file = 'report_{0}_{1}.txt'.format(shader_db.restriction,shader)
        shader_db.generate_report(shader, restrict_type)
    else:
        input("{} is missing!  Press Enter to abort.".format(csv_file))