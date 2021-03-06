# from http://www.daniweb.com/software-development/python/code/216651/wxpython-combobox-demo

    # use wxPython's wx.ComboBox() to select different units of measurement
    # then convert the area associated with the selections
    # tested with Python24 and wxPython26 vegaseat 21oct2005
import wx
class MyPanel(wx.Panel):
    """
    class MyPanel creates a panel with 2 comboboxes and more, inherits wx.Panel
    (putting your components/widgets on a panel gives additional versatility)
    """
    def __init__(self, parent, id):
    # no pos and size given, so panel defaults to fill the parent frame
        wx.Panel.__init__(self, parent, id)
        self.SetBackgroundColour((255,228,196)) # bisque
    # no size given, so the text determines the needed label size
        wx.StaticText(self, -1, "convert from:", (10, 10))
    # create a combo box to select units of measurement to convert from
        self.combo1 = wx.ComboBox(self, -1, value=areaList[0], pos=wx.Point(10, 30),
                                  size=wx.Size(120,30), choices=areaList)
    # optional tooltip
        self.combo1.SetToolTip(wx.ToolTip("select unit from dropdown-list"))
        wx.StaticText(self, -1, "convert to:", pos=wx.Point(150, 10))
    # create a combo box to select units of measurement to convert to
        self.combo2 = wx.ComboBox(self, -1, value=areaList[0], pos=wx.Point(150, 30),
                                  size=wx.Size(120, 30), choices=areaList)
        wx.StaticText(self, -1, "value to convert:", pos=wx.Point(10, 70))
        self.edit1 = wx.TextCtrl(self, -1, value="1", pos=wx.Point(10, 90), size=wx.Size(175, 25))
        self.edit1.SetBackgroundColour((255,255,197)) # suds yellow
        self.button1 = wx.Button(self, -1, label="Do the Conversion ...",
                                 pos=wx.Point(10, 130), size=wx.Size(175, 28))
    # respond to button click event
        self.button1.Bind(wx.EVT_BUTTON, self.button1Click, self.button1)
        wx.StaticText(self, -1, "result:", (10, 170))
        self.edit2 = wx.TextCtrl(self, -1, value="", pos=wx.Point(10, 190), size=wx.Size(350, 25))
        self.edit2.SetBackgroundColour((217,255,219)) # vegaseat green
    def button1Click(self,event):
        """Conversion button has been clicked"""
        unit1 = self.combo1.GetValue()
        unit2 = self.combo2.GetValue()
        x = float(self.edit1.GetValue())
        y = convertArea(x, unit1, unit2)
        if y < 0.001:
                str1 = "%f %s = %0.12f %s" % (x, unit1, y, unit2) # very small y
        elif y > 1000:
            str1 = "%f %s = %0.3f %s" % (x, unit1, y, unit2) # very large y
        else:
            str1 = "%f %s = %f %s" % (x, unit1, y, unit2) # 6 decimals is default
        self.edit2.SetValue(str1)
def convertArea(x, unit1, unit2):
        """convert area x of unit1 to area of unit2 and return area, on error return False"""
        if (unit1 in areaD) and (unit2 in areaD):
            factor1 = areaD[unit1]
            factor2 = areaD[unit2]
            return factor2*x/factor1
        else:
            return False
    #create an empty dictionary
areaD = {}
        # populate dictionary with units and conversion factors relative to sqmeter = 1.0
        # this minimizes the total number of conversion factors
areaD['sqmeter'] = 1.0
areaD['sqmillimeter'] = 1000000.0
areaD['sqcentimeter'] = 10000.0
areaD['sqkilometer'] = 0.000001
areaD['hectare'] = 0.0001
areaD['sqinch'] = 1550.003
areaD['sqfoot'] = 10.76391
areaD['sqyard'] = 1.19599
areaD['acre'] = 0.0002471054
areaD['sqmile'] = 0.0000003861022
# create a sorted list for the combo boxes
areaList = sorted(areaD.keys())
app = wx.PySimpleApp()
# create a window/frame, no parent, -1 is default ID, title, size
frame = wx.Frame(None, -1, "Convert Area ...", size = (400, 300))
# call the derived class, -1 is default ID, can also use wx.ID_ANY
MyPanel(frame,-1)
# show the frame
frame.Show(True)
# start the event loop
app.MainLoop()

