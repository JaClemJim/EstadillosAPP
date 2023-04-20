import os

class MyOutput:
    def __init__(self,nombreFile):
        self.nombreFile=nombreFile
        
        self.txt=""
        
    def añadirResultados(self,txt):
        #self.txt=self.txt + '\r\n' + txt
        if self.txt=="":
            self.txt=txt
        else:
            self.txt=self.txt + '\n' + txt
        
    def volcarResultados(self,overwrite=True):
        if overwrite:
            parametro="w"
        else:
            parametro="a"
        f = open(self.nombreFile, parametro)
        f.write(self.txt)
        f.close()

