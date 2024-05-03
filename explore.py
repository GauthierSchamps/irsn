import re
import uuid
import subprocess
import matplotlib.pyplot as plt

global data_count

global file_count

global row_count

global module_count

module_count = 0

row_count = 0

data_count = 0

file_count = 0

all_modules = [] #Also includes sub_modules

file_db = 'chemin_jdd2.txt' #File containing all paths to .pel files 

file_response = 'resp.txt' #File which will contains the response of the programm /!\ Existing content will be overwritten

global_variables = {}

file_analysed = []

data_obtained = []

module_obtained = []

def read_file_func(file_path, encoding='utf-8', leng=1024):
    count_char = subprocess.run(['wc', '-m', file_path], text=True, capture_output=True).stdout.split()[0]
    
    with open(file_path, 'rb') as file:
        buffer = b''  
        
        while True and int(file.tell()) < int(count_char):
            container = file.read(leng)
            if not container and not buffer:
                break  # Fin du fichier

            buffer += container

            try:
                temp = buffer.decode(encoding)
                lines = temp.splitlines(keepends=True)

                if lines[-1].endswith('\n'):
                    yield from lines[:-1]
                    buffer = lines[-1].encode(encoding)
                    
                else:
                    buffer = temp.encode(encoding)
            except UnicodeDecodeError as e:
                # Retour à la dernière ligne valide avant le problème
                valid_text = buffer[:e.start].decode(encoding, errors='ignore')
                yield from valid_text.splitlines(keepends=True)
                # Avancer après le byte problématique
                file.seek(e.start + 1 - len(buffer), 1)
                
                buffer = b''

        if buffer:
            yield buffer.decode(encoding, errors='ignore')

class module_pel:
    def __init__(self, name, condition=None, parent=None):
        global module_count
        module_count += 1
        self.name = name
        self.sub_modules = []
        self.parent = parent
        self.affectations = {} # Key : name of the affectation | Value : class affectation related
        self.inclusions = [] #All #include() elements
        self.conditions = condition  # If a condition is required to launch the module (especially for sub_modules), None else 
        all_modules.append(self)
        self.appearance = 1 # Keep in track how many time we met that module to estimate frequency at the end
        if parent is not None:
            parent.addSub(self)
            
    def addAffectation(self, aff):
        dic = self.affectations.get(aff['name'])
        if dic is None:
            self.affectations[aff['name']] = affectation(aff['name'],aff['value'])
        else:
            dic.found()
        self.affectations[aff['name']].add(aff['value'])

    def addSub(self, module):
        self.sub_modules.append(module)
        
    def getName(self):
        return self.name
        
class affectation:
    def __init__(self,name,module):
        self.name = name
        self.values = set()
        self.module = module
        self.appearance = 1
        
    def add(self,value):
        global data_count
        if value not in self.values:
            data_count += 1
            self.values.add(value)
        
    def getValue(self):
        resp = []
        for value in self.values:
            resp.append(value)
        return resp
    def display(self):
        resp = "["
        freq = self.appearance / file_count * 100
        freq_txt = f"({freq:.2f}%)"
        values_list = list(self.values)
        for i in range(len(values_list)):
            if i > 0:
                resp += ", "
            resp += str(values_list[i])
            resp += "]"
            resp = self.name + " " + freq_txt +" = "+ resp
        return resp
    
    def found(self):
        self.appearance += 1
    
def convert_value_explicit(value,dictionary):
    # Use this fonction for replace global variables by their value keeping their original name
    
    unique_marker = str(uuid.uuid4())  # Création d'un marqueur unique
    escaped_dictionary = {key: val.replace('$', unique_marker) for key, val in dictionary.items()}
    
    # Substitution of variables
    pattern = re.compile(r'\$(\w+)')
    words = re.findall(pattern, value)
    words = sorted(words, key=len, reverse=True)  # Trier par longueur décroissante pour éviter des substitutions partielles
    resp = value
    for word in words:
        var_name = '$' + word
        replacement_text = '§' + word
        if var_name in escaped_dictionary:
            replacement_text += ' (= ' + escaped_dictionary[var_name] + ')'
        else:
            replacement_text += '(not defined)'
            
        
        resp = resp.replace(var_name, replacement_text)
    
    resp = resp.replace(unique_marker, '$')
    return resp
    
def row_type(row):
    if 'END MODULE' in row:		
        return 'closer'
    elif "#include" in row:
        return 'inclusion'
    elif row.strip() == "" or "MODULE PEL_Application" in row: #This Module is the container of all others, we dont consider it
        return 'empty'
    elif 'MODULE' in row:
        return 'opener'
    elif row.strip()[0] == "$":
        return 'global_variable'
    elif row.strip().startswith('if'):
        return 'condition'
    elif "=" in row:
        return 'affectation'
    elif '//' in row:
        return 'comment'
    else:
        return None 

def check_concat(row):
    #Preventing code error due to vector's concatenation, array etc...
    return row_type(row) is None 
    
def get_module(name,cond,parent):
    # We search if the module exists
    if parent is not None:
        for mod in parent.sub_modules:
            if mod.name == name:
                mod.appearance += 1
                return mod
    
    else:
        for mod in all_modules:
            if mod.name == name and mod.parent is None:
                mod.appearance += 1
                return mod
                
    # If not, we create a new one
    return module_pel(name,cond,parent)
    
           
    
def deal_module(lines,cond,parent=None):
	# return count of line inside of the module as integer and module created as module_pel

    name = get_module_name(lines[0])
    i = 1
    mod = get_module(name,cond,parent)
    cond = None
    while i < len(lines[1:]):
        line = lines[i].rstrip().lstrip()
        line_type = row_type(line)
        if line_type == 'closer':
            return (i + 2), mod 
        elif line_type == 'inclusion':
            i += 1
            mod.inclusions.append(line.rstrip().lstrip())
        elif line_type == 'opener':
            dealing = deal_module(lines[i:],cond,mod)
            jump = dealing[0]
            
            i += jump
        elif line_type == 'empty':
            i += 1
        elif line_type == 'global_variable':
            while check_concat(lines[i + 1]):
                try:
                    line = line.rstrip().lstrip() + lines[i + 1].rstrip().lstrip()             
                except MemoryError:
                    line = line[:-4].rstrip().lstrip() + "..."
                finally:
                    i += 1
            stripted = line.strip()
            splited = stripted.split('=')
            try:
                global_variables[splited[0].strip()] = splited[1]
            except IndexError:
                print(line)
            i += 1
        elif line_type == 'affectation':
            
            while check_concat(lines[i + 1]):
                
                line = line.rstrip().lstrip() + (lines[i + 1]).rstrip().lstrip()
                i += 1
            ppties = get_aff_ppties(line)
            aff = mod.addAffectation(ppties)
			
            i += 1

        elif line_type == 'condition':
            cond = get_cond(line)
            i += 1
            continue
        else:
            i += 1
        cond = None    
    return i, mod
	
def get_aff_ppties(line):
    stripted = line.strip().split('=')
    try:
        return {
	    	'name':stripted[0],
	    	'value':stripted[1]
	    	}	
    except IndexError as e:
        return None	 
def get_module_name(row):
    return row.strip()[7:]

def get_cond(row):
    return row.strip()[2:-1]
	
def main():

    global file_count
    global data_count
    global module_count
     
    # Getting files 
    filenames = list(read_file_func(file_db))
    
	
    for filename in filenames:
    
        if (file_count % 1000) == 0:
            file_analysed.append(file_count)
            data_obtained.append(data_count)
            module_obtained.append(module_count)
        file_count += 1
        
        file_affectations = {} #Keep a track of all local affectation
		
        global row_count 
        filename = filename.replace("\n","")
        
        lines = list(read_file_func(filename))
        global_variables = {} #Key: variable's name ,Value : variables,value
		
        row_count += len(lines)
        i = 0
        cond = None
        while i < len(lines):
            
            line = lines[i].rstrip().lstrip()
            line_type = row_type(line)
            if line_type == 'opener':
                jump = deal_module(lines[i:],cond)[0] 
                i += jump 
            elif line_type == 'empty':
                i += 1
                continue
            elif line_type == 'global_variable':
                while check_concat(lines[i + 1]):
                    
                    try:
                        line = line.rstrip().lstrip() + lines[i].rstrip().lstrip()
                    except MemoryError:
                        line = line[:-4].rstrip().lstrip() + "..."
                    finally:
                        i+= 1
                stripted = line.strip()
                splited = stripted.split('=')
                try:
                    global_variables[splited[0].strip()] = splited[1]
                except IndexError:
                    print(line)
                i += 1
            elif line_type == 'condition':
                cond = get_cond(line)
                i += 1
                continue
            else:
                i += 1
            cond = None
		# Once dealing files is over, we convert global variables to her values
    
    for mod in all_modules:
        
        for affectations in mod.affectations:
            aff = mod.affectations[affectations]
            val_list = list(aff.values)
            for val in val_list:
                #Non explicit affectation
                aff.values.discard(val)    
                while "$" in val:
                    val = convert_value_explicit(val,global_variables)
                    
                aff.values.add(val)
		
	# Once all data are handled we display them in the .txt file
	# -> Introduce a module
	# $ Introduce an affectation (followed by a list of all possible values)
  # § Is used for data on the original pel file
    content = ""
    u = 0
    for _module in all_modules:
        
        if _module.parent is None:
            content += print_module(_module, 0)				
    with open(file_response , 'w') as fichier:
        fichier.write(content)

def print_module(mod,layer):
    global file_count 
    freq = mod.appearance / file_count * 100 
    freq_txt = f" ({freq:.2f}%) "
    resp = "\t" * layer + "-> " + mod.name + freq_txt +("" if mod.conditions is None else " (Condition: " + mod.conditions + ")") + ":\n"

    # Printing inclusions
    
    for inclusion in mod.inclusions:
        resp += "\t" * (layer + 1) + inclusion
			
	#Printing affectations

    for aff in mod.affectations:
        
        resp += "\t" * (layer + 1) + " $" + mod.affectations[aff].display() + "\n"
	
	#Printing submodules

    for sub_module in mod.sub_modules:
        resp += print_module(sub_module,layer + 1)
	
    return resp
	
if __name__ == '__main__':
    main()
    
    
    file_analysed.append(file_count)
    data_obtained.append(data_count)
    module_obtained.append(module_count)
    
    
    plt.plot(file_analysed, data_obtained, label='Data Obtained', marker='o')  # Tracer data_obtained
    plt.plot(file_analysed, module_obtained, label='Module Obtained', marker='s')  # Tracer module_obtained


    plt.xlabel('File Analysed')
    plt.ylabel('Values')
    plt.title('Data and Module Obtained vs. File Analysed')
    plt.legend()

    
    plt.grid(True)  
    plt.show()
    
    print(f" Files scanned : {file_count} ! \n Rows analyzed : {row_count} ! \n Data obtained : {data_count} !")
    
    # ----- END -----
    
    
    
