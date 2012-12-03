#!/usr/bin/env python
#    photo-print-prep
#    Copyright 2010-2010 Nick Klosterman <nick dot klosterman @t gmail dot com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

#FEATURES
# show at what % resolution you are viewing the image at.
# need to research if it is better to crop so it is close to the print resolutin (therfore no downsampling) or to keep resolution higher and pray for best when downsampling.
# put the resolution % and the filename and code in a status bar at the bottom and eliminate all but the image in the left view.
# prevent loading of images that are too small to print well. I.e. anything really less than 1200x800px that is if we believe what we saw on about.com about print resolutions. It says 140-200px for good, 200-300ppi for high res good prints.
# prevent zooming in? show at max normalized?
# multiple file format wildcards

import os
import sys
import datetime
import optparse
import re
import random
import tempfile
import logging
import subprocess
import shutil
import time
from logging import debug, warn, info
import wxversion
wxversion.select("2.8")
import wx
import wx.lib.newevent
from wx.lib.wordwrap import wordwrap

import glob

ProgName = 'photo-print-prep'
ProgVersion = '0.1'

# custom event
PictureControlDragEvent, EVT_PICTURE_CONTROL_DRAG_EVENT = wx.lib.newevent.NewEvent()

THUMBNAIL_SIZE_PX = 80 #48
PANEL_TO_IMAGE_SCALE = 1.0 # how big the panel is compared to image, 1 = image takes up full size; works 1/X so the greater the number the smaller the amount of the panel is taken up
LEFT_WINDOW_PIXEL_WIDTH = 90 #The number is the pixel width of the left window

# menu id
ID_EXIT = wx.NewId()
ID_SAVE = wx.NewId()
ID_SAVEAS = wx.NewId()
ID_NEWFILE = wx.NewId()
ID_OPENFILE = wx.NewId()
ID_OPENDIRECTORY = wx.NewId()
ID_GENERATESCRIPT = wx.NewId()
ID_GENERATESLIDESHOW = wx.NewId()
ID_EDITPREFS = wx.NewId()
ID_USAGE = wx.NewId()

ID_POPUP_KENBURNS = wx.NewId()
ID_POPUP_CROP = wx.NewId()
ID_POPUP_DELEFFECT = wx.NewId()
ID_POPUP_EDIT = wx.NewId()
ID_POPUP_ADDPICTURES = wx.NewId()
ID_POPUP_ADDSONGS = wx.NewId()
ID_POPUP_LQPREVIEW = wx.NewId()
ID_POPUP_HQPREVIEW = wx.NewId()
ID_POPUP_USEEDITOR = wx.NewId()

# file dialog wildcard
imageFileWildcard = "jpg files (*.jpg)|*.jpg|" \
                    "jpeg files (*.jpeg)|*.jpeg|" \
                    "jpeg files (*.JPG)|*.JPG|" \
                    "All files (*.*)|*.*|"

dvdSlideshowScript = "dvd-slideshow files (*.txt)|*.txt|" \
                     "All files (*.*)|*.*|"

def positiveOrZero(number):
   return (number,0)[number<0]

def getImageFromScriptLine(line):
   imageFileExt = [i.rstrip('|').strip('|*.') for i in re.findall(r'\|\*\..+?\|', imageFileWildcard) if i != '|*.*|']
   pictPath = line.split(':')[0]
   base, ext = os.path.splitext(pictPath)
   if (ext.lstrip('.').lower() in imageFileExt) and os.path.exists(pictPath):
      return pictPath
   else:
      return None


class PictureControl(wx.Control):

   # some constants
   cPanelToImageScale = PANEL_TO_IMAGE_SCALE  # how big the panel is compared to image

   def __init__(self, parent, eventTarget, id=wx.ID_ANY, isWidescreen = False):
      wx.Control.__init__(self, parent, id)

      self.eventTarget = eventTarget
      # Bind events
      self.pictPath = None
      self.image = None
      self.desiredAspect = (4.0/3, 16.0/9)[bool(isWidescreen)]
      self.isResized = True
      self.boxSelection = []
      self.dontDrawBoxAtIndex = None
      self.boxColour = [wx.Colour(255,255,255), wx.Colour(0,255,125)]
      self.textFG = wx.Colour(255,255,255)

      # this below is a bit annoying. I suppose we'll just use the help window for explanation.
      # self.SetToolTip(wx.ToolTip("alt: no snap, ctrl+alt: freeform"))

      self.Bind(wx.EVT_PAINT, self.onPaint)
      self.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBackground)
      self.Bind(wx.EVT_SIZE, self.onResize)

      wx.EVT_LEFT_DOWN(self, self.onMouseEvent)
      wx.EVT_LEFT_UP(self, self.onMouseEvent)
      wx.EVT_MOTION(self, self.onMouseEvent)

   def onResize(self, event):
      self.isResized = True
      self.Refresh()

   def onPaint(self, event):
      dc = wx.BufferedPaintDC(self) # use BufferedPaintDC to reduce flicker
      self.drawImage(dc)

   def scaleAndCenterImage(self, displayWidth, displayHeight):
      if self.pictPath: # means self.image is initialized
         displayAspect = float(displayWidth)/displayHeight
         if displayAspect > self.desiredAspect:
            imageDisplayWidth = (displayHeight / self.cPanelToImageScale) * self.desiredAspect
            self.imageScale = imageDisplayWidth / self.image.GetWidth()
            self.scaledImageBitmap = wx.BitmapFromImage(self.image.Scale(imageDisplayWidth, displayHeight/self.cPanelToImageScale))
            self.offsetToScaledImage = (round((displayWidth-imageDisplayWidth)/2), round((displayHeight * (1-(1/self.cPanelToImageScale)))/2))
         else:
            imageDisplayHeight = (displayWidth / self.cPanelToImageScale) / self.desiredAspect
            self.imageScale = imageDisplayHeight / self.image.GetHeight()
            self.scaledImageBitmap = wx.BitmapFromImage(self.image.Scale(displayWidth/self.cPanelToImageScale, imageDisplayHeight))
            self.offsetToScaledImage = (round((displayWidth * (1-(1/self.cPanelToImageScale)))/2), round((displayHeight-imageDisplayHeight)/2))

   def drawRectangle(self, dc, id, x, y, w, h):
      dc.SetBrush(wx.Brush(wx.Colour(255,255,255), wx.TRANSPARENT))
      # dc.SetLogicalFunction(wx.XOR)  # This makes it looks bad
      dc.SetPen(wx.Pen(self.boxColour[id], 1, wx.SOLID))
      dc.DrawRectangle(x,y,w,h)

      # should we put the number or some description on the rectangle?
      # dc.SetTextForeground(self.textFG)
      # dc.DrawText(str(id),(x+w)/2,y)

      # now draw the mouse-control boxes, move and resize control
      mouseControlBoxSize = 10
      dc.SetBrush(wx.Brush(self.boxColour[id], wx.SOLID))
      dc.SetPen(wx.Pen(self.boxColour[id], 1, wx.SOLID))

      moveRegion = wx.Region(x,y,mouseControlBoxSize,mouseControlBoxSize)
      self.mouseControlRegions[id*2] = moveRegion
      dc.DrawRectangle(moveRegion.GetBox().x, moveRegion.GetBox().y, moveRegion.GetBox().width, moveRegion.GetBox().height)

      resizeRegion = wx.Region(x+w-mouseControlBoxSize-1,y+h-mouseControlBoxSize-1,mouseControlBoxSize,mouseControlBoxSize)
      self.mouseControlRegions[(id*2)+1] = resizeRegion
      dc.DrawRectangle(resizeRegion.GetBox().x, resizeRegion.GetBox().y, resizeRegion.GetBox().width, resizeRegion.GetBox().height)

   def translateCoordinateRealPictToPanel(self, x, y):
      return (round(((x+self.offsetToRealImage[0])*self.imageScale)+self.offsetToScaledImage[0]), round(((y+self.offsetToRealImage[1])*self.imageScale)+self.offsetToScaledImage[1]))

   def translateCoordinatePanelToRealPict(self, x, y):
      return (round(((x-self.offsetToScaledImage[0])/self.imageScale)-self.offsetToRealImage[0]), round(((y-self.offsetToScaledImage[1])/self.imageScale)-self.offsetToRealImage[1]))

   def translateCoordinateImageToPanel(self, x, y):
      return (round((x*self.imageScale)+self.offsetToScaledImage[0]), round((y*self.imageScale)+self.offsetToScaledImage[1]))

   def translateCoordinatePanelToImage(self, x, y):
      return (round((x-self.offsetToScaledImage[0])/self.imageScale), round((y-self.offsetToScaledImage[1])/self.imageScale))

   def translateDimensionImageToPanel(self, w, h):
      return (round(w*self.imageScale), round(h*self.imageScale))

   def translateDimensionPanelToImage(self, w, h):
      return (round(w/self.imageScale), round(h/self.imageScale))

   def drawBoxes(self, dc):
      for id,box in enumerate(self.boxSelection):
         if id != self.dontDrawBoxAtIndex:

            x,y = self.translateCoordinateImageToPanel(box[0][0], box[0][1])
            w,h = self.translateDimensionImageToPanel(box[1][0], box[1][1])

            # draw the rectangle
            self.drawRectangle(dc,id,x,y,w,h)

   def drawImage(self, dc):
      width, height = self.GetClientSize()
      if not width or not height:
         return  # we still don't have dimensions

      bg = self.GetBackgroundColour()
      bgBrush = wx.Brush(bg, wx.SOLID)
      dc.SetBackground(bgBrush)
      dc.Clear()

      # reserve enough mouseControlRegions list. Each box would have 2 of these
      self.mouseControlRegions = [None] * len(self.boxSelection) * 2

      if self.pictPath: # means self.image is initialized
         if self.isResized:
            self.isResized = False
            self.scaleAndCenterImage(width, height)

         dc.DrawBitmap(self.scaledImageBitmap, self.offsetToScaledImage[0], self.offsetToScaledImage[1])
         self.drawBoxes(dc)
      else:
         dc.DrawBitmap(wx.EmptyBitmap(1,1), 0, 0)

      return dc

   def onEraseBackground(self, event):
      # This is intentionally empty, because we are using the combination of
      # wx.BufferedPaintDC + empty onEraseBackground event to reduce flicker
      pass

   def loadImageIntoDesiredAspectRatio(self):
      self.image = wx.Image(self.pictPath) #.Rotate90(True)
      pictWidth = self.image.GetWidth()
      pictHeight = self.image.GetHeight()
      if pictWidth < pictHeight:
         self.image = wx.Image(self.pictPath).Rotate90(True)
         pictWidth = self.image.GetWidth()
         pictHeight = self.image.GetHeight()
      self.pictDimension = (pictWidth, pictHeight)
      self.pictAspect = float(pictWidth) / pictHeight
      if self.desiredAspect > self.pictAspect:
         desiredWidth = pictHeight * self.desiredAspect
         offset = round((desiredWidth - pictWidth)/2)
         self.image.Resize(wx.Size(desiredWidth, pictHeight), wx.Point(offset, 0), 0, 0, 0)
         self.offsetToRealImage = (offset,0)
         self.onePercentDimension = (desiredWidth / 100.0, pictHeight / 100.0)
      else:
         desiredHeight = pictWidth / self.desiredAspect
         offset = round((desiredHeight - pictHeight)/2)
         self.image.Resize(wx.Size(pictWidth, desiredHeight), wx.Point(0, offset), 0, 0, 0)
         self.offsetToRealImage = (0,offset)
         self.onePercentDimension = (pictWidth / 100.0, desiredHeight / 100.0)

   def addBoxSelection(self, param):
      p = [i.strip() for i in param.split(';')]
      if re.match(r'\d+,\d+', p[0]):
         # using the absolute coordinate
         x0,y0 = p[0].split(',')
         x1,y1 = p[1].split(',')
         self.boxSelection.append(((int(x0) + self.offsetToRealImage[0],int(y0) + self.offsetToRealImage[1]),\
            (int(x1)-int(x0),int(y1)-int(y0))))
      else:
         # using keyword description in this block
         # decode frame_size
         if re.match(r'\d+%', p[0]):
            scale = int(p[0].rstrip('%')) / 100.0
            # using zoom percentage
            if self.desiredAspect > self.pictAspect:
               h = int(self.image.GetHeight() * scale)
               w = int(h * self.desiredAspect)
            else:
               w = int(self.image.GetWidth() * scale)
               h = int(w / self.desiredAspect)
         elif p[0] == 'imageheight':
            h = self.pictDimension[1]
            w = int(h * self.desiredAspect)
         elif p[0] == 'imagewidth':
            w = self.pictDimension[0]
            h = int(w / self.desiredAspect)
         else:
            warning("WARNING: don't know how to parse crop/kenburns parameter: %s" % param)
            return

         # decode frame_location
         if re.match(r'\d+%', p[1]):
            # percentage here is the coordinate of the frame's center point
            # according to the percentage of the dvd window (I think..)
            x_center = round(int(p[1].split(',')[0].strip().rstrip('%')) * self.image.GetWidth() / 100.0)
            y_center = round(int(p[1].split(',')[1].strip().rstrip('%')) * self.image.GetHeight() / 100.0)
            x_offset = x_center - (w/2)
            y_offset = y_center - (h/2)
         else:
            # decode word location
            if p[1].endswith('left'):
               x_offset = 0
            elif p[1].endswith('right'):
               x_offset = self.image.GetWidth() - w
            else:
               x_offset = (self.image.GetWidth() - w)/2

            if p[1].startswith('top'):
               y_offset = 0
            elif p[1].startswith('bottom'):
               y_offset = self.image.GetHeight() - h
            else:
               y_offset = (self.image.GetHeight() - h)/2

         self.boxSelection.append([(x_offset, y_offset), (w,h)])

   def addCrop(self, param):
      self.addBoxSelection(param)

   def addKenburns(self, param):
      p = param.split(';')
      self.addBoxSelection(';'.join([p[0],p[1]]))
      self.addBoxSelection(';'.join([p[2],p[3]]))

   def displayScriptLine(self, scriptLine):
      lineElems = scriptLine.split(':')
      self.pictPath = getImageFromScriptLine(scriptLine)
      if self.pictPath:
         self.loadImageIntoDesiredAspectRatio()
         self.isResized = True # set isResized, so draw() would rescale image
         self.boxSelection = []
         self.dontDrawBoxAtIndex = None

         # decode pict params
         # image.jpg:dur:sub:effect (effect can be crop or kenburns, each with their own param)
         # In the display, we care more on the effect
         if (len(lineElems) > 4):
            if lineElems[3] == 'crop':
               self.addCrop(lineElems[4])
            elif lineElems[3] == 'kenburns':
               self.addKenburns(lineElems[4])

      self.Refresh()

   def setWidescreen(self, isWidescreen):
      self.desiredAspect = (4.0/3, 16.0/9)[isWidescreen]
      self.loadImageIntoDesiredAspectRatio()
      self.isResized = True # set isResized, so draw() would rescale image
      self.Refresh()

   def calculateSnap(self, x, y, w, h, isSnapToKeyword, isAspect = True):

      def withinTolerance(num, target, tolerance):
         return ((target - tolerance/2) <= num) and (num < (target + tolerance/2))

      assert not isSnapToKeyword or isAspect, 'snap to keyword must also follow aspect ratio'

      if isAspect:
         # fixup the box selection to desired aspect ratio
         boxAspect = float(w)/(max(h,1))  # use max trick so we don't do division by 0
         if self.desiredAspect > boxAspect:
            w = h * self.desiredAspect
         else:
            h = w / self.desiredAspect

      panelOnePercentDimension = (self.onePercentDimension[0] * self.imageScale, self.onePercentDimension[1] * self.imageScale)
      if isSnapToKeyword:
         # deal with w,h first, since it's easier
         framePercentage = min(round(w / panelOnePercentDimension[0]),100)
         w = round(min(round(w / panelOnePercentDimension[0]),100) * panelOnePercentDimension[0])
         h = round(min(round(h / panelOnePercentDimension[1]),100) * panelOnePercentDimension[1])

         # we prefer using imageheight or imagewidth keyword for the script, so
         # see if we can snap to that
         if withinTolerance(w, self.pictDimension[0] * self.imageScale, panelOnePercentDimension[0]):
            frameSizeStr = 'imagewidth'
         elif withinTolerance(h, self.pictDimension[1] * self.imageScale, panelOnePercentDimension[1]):
            frameSizeStr = 'imageheight'
         else:
            frameSizeStr = '%d%%' % framePercentage

         # now deal with the position.
         # we prefer using the positional keyword rather than percent. So calculate that first
         topLeftCoord = self.translateCoordinateImageToPanel(0,0)
         middleCoord = self.translateCoordinateImageToPanel(self.image.GetWidth()/2,self.image.GetHeight()/2)
         bottomRightCoord = self.translateCoordinateImageToPanel(self.image.GetWidth(),self.image.GetHeight())
         if withinTolerance(x, topLeftCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y, topLeftCoord[1], panelOnePercentDimension[1]):
            x,y = topLeftCoord
            framePosStr = 'topleft'
         elif withinTolerance(x, topLeftCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y+(h/2), middleCoord[1], panelOnePercentDimension[1]):
            x,y = topLeftCoord[0], middleCoord[1]-(h/2)
            framePosStr = 'left'
         elif withinTolerance(x, topLeftCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y+h, bottomRightCoord[1], panelOnePercentDimension[1]):
            x,y = topLeftCoord[0], bottomRightCoord[1]-h
            framePosStr = 'bottomleft'
         elif withinTolerance(x+(w/2), middleCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y, topLeftCoord[1], panelOnePercentDimension[1]):
            x,y = middleCoord[0]-(w/2), topLeftCoord[1]
            framePosStr = 'top'
         elif withinTolerance(x+(w/2), middleCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y+(h/2), middleCoord[1], panelOnePercentDimension[1]):
            x,y = middleCoord[0]-(w/2), middleCoord[1]-(h/2)
            framePosStr = 'middle'
         elif withinTolerance(x+(w/2), middleCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y+h, bottomRightCoord[1], panelOnePercentDimension[1]):
            x,y = middleCoord[0]-(w/2), bottomRightCoord[1]-h
            framePosStr = 'bottom'
         elif withinTolerance(x+w, bottomRightCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y, topLeftCoord[1], panelOnePercentDimension[1]):
            x,y = bottomRightCoord[0]-w, topLeftCoord[1]
            framePosStr = 'topright'
         elif withinTolerance(x+w, bottomRightCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y+(h/2), middleCoord[1], panelOnePercentDimension[1]):
            x,y = bottomRightCoord[0]-w, middleCoord[1]-(h/2)
            framePosStr = 'right'
         elif withinTolerance(x+w, bottomRightCoord[0], panelOnePercentDimension[0]) and \
               withinTolerance(y+h, bottomRightCoord[1], panelOnePercentDimension[1]):
            x,y = bottomRightCoord[0]-w, bottomRightCoord[1]-h
            framePosStr = 'bottomright'
         else:
            # Remember that the percentage position in
            # dvd-slideshow refers to the center point of the selection, which
            # makes it more interesting -- more math :(
            centerx = x + (w/2)
            centery = y + (h/2)
            xpercentage = max(min(round((centerx - self.offsetToScaledImage[0])/panelOnePercentDimension[0]),100),0)
            ypercentage = max(min(round((centery - self.offsetToScaledImage[1])/panelOnePercentDimension[1]),100),0)
            centerx = round(xpercentage * panelOnePercentDimension[0]) + self.offsetToScaledImage[0]
            centery = round(ypercentage * panelOnePercentDimension[1]) + self.offsetToScaledImage[1]
            x = centerx - (w/2)
            y = centery - (h/2)
            framePosStr = '%d%%,%d%%' % (xpercentage, ypercentage)

         paramStr = ';'.join([frameSizeStr,framePosStr])

      else:
         # we're just using raw coordinate in this case
         stx, sty = self.translateCoordinatePanelToRealPict(x,y)
         endx, endy = self.translateCoordinatePanelToRealPict(x+w,y+h)
         paramStr = '%d,%d;%d,%d' % (stx, sty, endx, endy)

      return (x, y, w, h, paramStr)

   def onMouseEvent(self, event):

      mousePos = event.GetPosition()

      if self.pictPath == None:
         return # if there's nothing displayed, just return

      if event.LeftUp() and (self.mouseInRegionIndex != None):
         # user just released the mouse button. Finalize selection
         box_id = self.mouseInRegionIndex/2
         if self.mouseInRegionIndex % 2:
            # resize operation
            x,y = self.translateCoordinateImageToPanel(self.boxSelection[box_id][0][0], self.boxSelection[box_id][0][1])
            w,h = (positiveOrZero(mousePos.x-x), positiveOrZero(mousePos.y-y))
            x,y,w,h,str = self.calculateSnap(x,y,w,h, not event.AltDown(), not (event.AltDown() and event.ControlDown()))
            self.boxSelection[box_id][0] = self.translateCoordinatePanelToImage(x,y)
            self.boxSelection[box_id][1] = self.translateDimensionPanelToImage(w,h)
         else:
            # move operation
            w,h = self.translateDimensionImageToPanel(self.boxSelection[box_id][1][0], self.boxSelection[box_id][1][1])
            x,y,w,h,str = self.calculateSnap(mousePos.x,mousePos.y,w,h, not event.AltDown(), not (event.AltDown() and event.ControlDown()))
            self.boxSelection[box_id][0] = self.translateCoordinatePanelToImage(x,y)
            self.boxSelection[box_id][1] = self.translateDimensionPanelToImage(w,h)

         postEvent = PictureControlDragEvent(box = box_id, param = str)
         wx.PostEvent(self.eventTarget, postEvent)

         self.dontDrawBoxAtIndex = None
         self.mouseInRegionIndex = None

      if not event.LeftIsDown():
         # user is just moving mouse around, so we only need to change mouse
         # cursor here depending on where it is
         for i,region in enumerate(self.mouseControlRegions):
            if region:
               if region.Contains(mousePos.x, mousePos.y):
                  self.SetCursor(wx.CROSS_CURSOR)
                  self.mouseInRegionIndex = i
                  break
         else:
            self.SetCursor(wx.STANDARD_CURSOR)
            self.mouseInRegionIndex = None

      if event.Dragging() and event.LeftIsDown() and (self.mouseInRegionIndex != None):
         # dragging, now is the hard work of redrawing the screen with changing the box
         if self.mouseInRegionIndex != None:
            box_id = self.mouseInRegionIndex/2
            self.dontDrawBoxAtIndex = box_id # invoke draw, but don't draw the current box manipulated
            dc = wx.BufferedPaintDC(self)
            dc = self.drawImage(dc)

            if self.mouseInRegionIndex % 2:
               # resize operation
               x,y = self.translateCoordinateImageToPanel(self.boxSelection[box_id][0][0], self.boxSelection[box_id][0][1])
               w,h = (positiveOrZero(mousePos.x-x), positiveOrZero(mousePos.y-y))
               x,y,w,h,str = self.calculateSnap(x,y,w,h, not event.AltDown(), not (event.AltDown() and event.ControlDown()))
               self.drawRectangle(dc, box_id, x, y, w, h)
            else:
               # move operation
               w,h = self.translateDimensionImageToPanel(self.boxSelection[box_id][1][0], self.boxSelection[box_id][1][1])
               x,y,w,h,str = self.calculateSnap(mousePos.x,mousePos.y,w,h, not event.AltDown(), not (event.AltDown() and event.ControlDown()))
               self.drawRectangle(dc, box_id, x, y, w, h)

            postEvent = PictureControlDragEvent(box = box_id, param = str)
            wx.PostEvent(self.eventTarget, postEvent)


class ListDropTarget(wx.TextDropTarget):
   def __init__(self, dropTarget):
      wx.TextDropTarget.__init__(self)
      self.dropTarget = dropTarget

      # specify the type of data we will accept
      self.data = wx.TextDataObject()
      self.SetDataObject(self.data)

   def OnDropText(self, x, y, d):
      self.dropTarget.onDrop(x, y, self.data.GetText())
      return d

class MainWindow(wx.Frame):
   """
   Main Window
   """
   imageListBitmapSize = THUMBNAIL_SIZE_PX 

   def __init__(self, parent, id, title, options, scriptPath):

      # Setup Window
      wx.Frame.__init__(self, parent, id, title)

      self.options = options

      self.imageList = wx.ImageList(self.imageListBitmapSize,self.imageListBitmapSize)
      self.imagePathList = []
      self.imageDimensionList = []

      # setup and create child windows

      self.vsplitter = wx.SplitterWindow(self, 2, style=wx.SP_3D)
      self.leftSizer = wx.BoxSizer(wx.VERTICAL)
      self.rightSizer = wx.BoxSizer(wx.VERTICAL)
      self.scriptView = wx.ListCtrl(self.vsplitter, 4, style = wx.LC_REPORT | wx.LC_EDIT_LABELS | wx.LC_NO_HEADER)
      self.imagePanel = PictureControl(self.vsplitter, self, 5, options.widescreen)
      self.scriptView.SetSizer(self.leftSizer)
      self.imagePanel.SetSizer(self.rightSizer)
      self.leftSizer.Add(self.scriptView, 1, wx.EXPAND)
      self.rightSizer.Add(self.imagePanel, 1, wx.EXPAND)
      self.vsplitter.SetMinimumPaneSize(20)

      self.overallSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.overallSizer.Add(self.vsplitter, 1, wx.EXPAND)
      self.SetSizer(self.overallSizer)
      self.SetAutoLayout(1)

      # menu
      menu = wx.Menu()
      menu.Append(ID_NEWFILE, "&New", "Start with a new script")
      menu.Append(ID_OPENFILE, "&Open...", "Open an existing script")
      menu.Append(ID_OPENDIRECTORY, "Open &Directory...", "Open a directory")
      menu.Append(ID_SAVE, "&Save", "Save the current script")
      menu.Append(ID_SAVEAS, "&Save as...", "Save script as another file")
      menu.AppendSeparator()
      menu.Append(ID_GENERATESLIDESHOW, "&Generate Slideshow...", "Start generating slideshow")
      menu.AppendSeparator()
      menu.Append(ID_EXIT, "E&xit", "Exit program")
      menubar = wx.MenuBar()
      menubar.Append(menu, "&File")

      # TODO: Dunno what should be in there just yet
      #menu = wx.Menu()
      #menu.Append(ID_EDITPREFS, "&Preferences...", "Edit preferences")
      #wx.EVT_MENU(self, ID_EDITPREFS, self.onEditPreferences)
      #menubar.Append(menu, "&Edit")

      menu = wx.Menu()
      menu.Append(ID_USAGE, "About/&Usage", "Display about box containing usage info")
      wx.EVT_MENU(self, ID_USAGE, self.onUsage)
      menubar.Append(menu, "&Help")
      self.SetMenuBar(menubar)

      self.popupMenu = wx.Menu()
      self.popupMenu.Append(ID_POPUP_KENBURNS, "Add Random Kenburns", "Selectively add random kenburns effect to selected lines")
      self.popupMenu.Append(ID_POPUP_CROP, "Add Crop Effect", "Selectively add crop effect to selected lines")
      self.popupMenu.Append(ID_POPUP_DELEFFECT, "Remove Picture Effect", "Remove all picture effect from the selected lines")
      self.popupMenu.Append(ID_POPUP_EDIT, "Edit Line", "Edit currently focused line")
      self.popupMenu.AppendSeparator()
      self.popupMenu.Append(ID_POPUP_LQPREVIEW, "Low Quality Preview", "Preview selected lines")
      self.popupMenu.Append(ID_POPUP_HQPREVIEW, "High Quality Preview", "Preview selected lines (slow compile)")
      self.popupMenu.AppendSeparator()
      self.popupMenu.Append(ID_POPUP_USEEDITOR, "Launch Default Editor...")

      # TODO: Still trying to figure out the semantics
      #self.popupMenu.Append(ID_POPUP_ADDPICTURES, "Add Pictures...")
      #self.popupMenu.Append(ID_POPUP_ADDSONGS, "Add Songs...")
      #wx.EVT_MENU(self, ID_POPUP_ADDPICTURES, self.onAddPicts)
      #wx.EVT_MENU(self, ID_POPUP_ADDSONGS, self.onAddSongs)

      # event binding
      wx.EVT_MENU(self, ID_NEWFILE, self.onNewFile)
      wx.EVT_MENU(self, ID_OPENFILE, self.onOpenFile)
      wx.EVT_MENU(self, ID_OPENDIRECTORY, self.onOpenDirectory)
      wx.EVT_MENU(self, ID_SAVE, self.onSave)
      wx.EVT_MENU(self, ID_SAVEAS, self.onSaveAs)
      wx.EVT_MENU(self, ID_EXIT, self.onExit)
      wx.EVT_MENU(self, ID_GENERATESLIDESHOW, self.onGenerateSlideshow)

      wx.EVT_MENU(self, ID_POPUP_KENBURNS, self.onAddKenburns)
      wx.EVT_MENU(self, ID_POPUP_CROP, self.onAddCrop)
      wx.EVT_MENU(self, ID_POPUP_DELEFFECT, self.onDelEffect)
      wx.EVT_MENU(self, ID_POPUP_EDIT, self.onEdit)
      wx.EVT_MENU(self, ID_POPUP_LQPREVIEW, self.onPreview)
      wx.EVT_MENU(self, ID_POPUP_HQPREVIEW, self.onPreview)
      wx.EVT_MENU(self, ID_POPUP_USEEDITOR, self.onUseEditor)

      self.Bind(wx.EVT_CLOSE, self.onCloseWindow)

      self.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.onLineFocused, self.scriptView)
      self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.onLineEdited, self.scriptView)
      self.Bind(wx.EVT_LIST_BEGIN_DRAG, self.onScriptViewDrag, self.scriptView)
      self.scriptView.Bind(wx.EVT_RIGHT_DOWN, self.onScriptRightClick)

      self.Bind(EVT_PICTURE_CONTROL_DRAG_EVENT, self.onPictControlSelectionDragged)

      dt = ListDropTarget(self)
      self.scriptView.SetDropTarget(dt)

      # load script to scriptView so it has some content that the vsplitter can give it some size
      if scriptPath:
         if os.path.isfile(scriptPath):
            self.setScriptPathAndLoad(scriptPath)
         else:
            self.setPictureDirectoryAndLoad(scriptPath)

      # this code below is only to test constructScriptLine()
      #for i,line in enumerate(open(self.scriptPath).readlines()):
      #   assert line == self.constructScriptLine(i), 'not equal: %s | %s' % (line, self.constructScriptLine(i))

      # finalize window sizes and display it
      self.vsplitter.SplitVertically(self.scriptView, self.imagePanel, LEFT_WINDOW_PIXEL_WIDTH) #The number is the pixel width of the left window
      self.overallSizer.Fit(self)
#set size of overall window
      self.SetSize(wx.Size(1024, 700)) # TODO: get this setting from last invocation
      self.Show(True)

   def onCloseWindow(self, event):
      if self.isUnsavedChanges and event.CanVeto():
         if not self.isContinueOrPromptForUnsavedChanges():
            event.Veto()
            return

      if hasattr(self, 'tempdir'):
         shutil.rmtree(self.tempdir, True) # remove tempdir, ignore error

      # else, just destroy the window and user might lose changes
      self.Destroy()

   def setScriptPathAndLoad(self, path):
      self.scriptPath = path
      #print ("self.scriptPath: " +self.scriptPath)
      if self.scriptPath:
         if os.path.isfile(scriptPath): #this is actually redundant since we shouldn't be here if it is a directory anyway.
            with open(self.scriptPath) as f:
               script = f.readlines()
            self.setUnsavedChanges(False)
            self.loadScript(script)
         else:
            print (self.scriptPath)
            self.loadDirectory(path)

   def setPictureDirectoryAndLoad(self, path):
      self.scriptPath = path
      #print ("self.scriptPath: " +self.scriptPath)
      if self.scriptPath:
         print (self.scriptPath)
         self.loadDirectory(path)
         self.setUnsavedChanges(False)
         
   def setUnsavedChanges(self, isChanged):
      if isChanged == False:
         # we set isUnsavedChanges to false rarely. We'll always set window title as well in this case
         self.isUnsavedChanges = False
         if self.scriptPath:
            self.SetTitle('photo-print-prep - %s' % self.scriptPath)
         else:
            self.SetTitle('photo-print-prep - untitled')
      else:
         # In this case, we set window title only when we transition from False
         if self.isUnsavedChanges == False:
            self.isUnsavedChanges = True
            if self.scriptPath:
               self.SetTitle('photo-print-prep - %s *' % self.scriptPath)
            else:
               self.SetTitle('photo-print-prep - untitled *')

   def isContinueOrPromptForUnsavedChanges(self):
      if self.isUnsavedChanges:
         dlg = wx.MessageDialog(self, 'You will lose any unsaved changes.\nDo you want to continue?',
               'Unsaved changes warning', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_EXCLAMATION)
         ret = (dlg.ShowModal() == wx.ID_YES)
         dlg.Destroy()
         return ret

      return True;

   def onNewFile(self, event):
      if self.isContinueOrPromptForUnsavedChanges():
         self.setScriptPathAndLoad(None)

   def onOpenFile(self, event):
      if self.isContinueOrPromptForUnsavedChanges():
         dlg = wx.FileDialog(self, message="Choose a dvd-slideshow script", defaultDir=os.getcwd(),
            defaultFile="", wildcard=dvdSlideshowScript, style=wx.OPEN | wx.CHANGE_DIR)

         # Show the dialog and retrieve the user response. If it is the OK response,
         # process the data.
         if dlg.ShowModal() == wx.ID_OK:
            debug('Opening dvd-slideshow script: %s' % self.scriptPath)
            self.setScriptPathAndLoad(dlg.GetPath())

         dlg.Destroy()

   def onOpenDirectory(self, event):
      dlg = wx.DirDialog(self, ("Choose a directory"), style=wx.DD_DEFAULT_STYLE|wx.CHANGE_DIR, defaultPath=os.getcwd())
      # Show the dialog and retrieve the user response. If it is the OK response,                                                                          
      # process the data.                                                                                                                                  
      if dlg.ShowModal() == wx.ID_OK:
            #FileList=wx.ListItem()
            #print (dlg.GetPath())
            #for infile in glob.glob(os.path.join(dlg.GetPath(), '*.jpg') ):
               #print ("file: " + infile)
               #FileList.SetText(infile)
            self.setPictureDirectoryAndLoad(dlg.GetPath())                                                                                                         
      dlg.Destroy()

   def onSave(self, event):
#      if self.scriptPath[len(self.scriptPath)-1] == '/':
      if os.path.isdir(self.scriptPath):
         self.onSaveAs(event)
      else:
         if self.scriptPath:
            with open(self.scriptPath, 'w') as f:
               f.writelines([self.constructScriptLine(i)+'\n' for i in range(self.scriptView.GetItemCount())])
               self.setUnsavedChanges(False)
         else:
            self.onSaveAs(event)

   def onSaveAs(self, event):
      dlg = wx.FileDialog(self, message="Save dvd-slideshow script as ...", defaultDir=os.getcwd(),
         defaultFile="", wildcard=dvdSlideshowScript, style=wx.SAVE | wx.CHANGE_DIR)

      # Show the dialog and retrieve the user response. If it is the OK response,
      # process the data.
      if dlg.ShowModal() == wx.ID_OK:
         self.scriptPath = dlg.GetPath()
         debug('Saving dvd-slideshow script as %s' % self.scriptPath)
         self.onSave(event)

      dlg.Destroy()

   def onExit(self, event):
      self.Close(True)

   def constructScriptLine(self, i):
      item = self.scriptView.GetItem(i)
      if item.GetImage() != -1:
         return self.imagePathList[item.GetImage()] + ':' + item.GetText()
      else:
         return item.GetText()

#      def loadDirectory(self, path):
#         for infile in glob.glob(os.path.join(dlg.GetPath(), '*.jpg') ):
#                                        print ("file: " + infile)
#                                        FileList.SetText(infile)

   def loadScript(self, script):
      # strip script of empty lines at the beginning and end of content
      while script[0].strip() == '':
         del script[0]
      while script[len(script)-1].strip() == '':
         del script[len(script)-1]

      # populate image list and path
      for line in script:
         imgFile = getImageFromScriptLine(line)
         print (imgFile)
         if imgFile:
            if imgFile not in self.imagePathList:
               img = wx.Image(imgFile)
               dimension = (img.GetWidth(), img.GetHeight())
               imgAspect = float(img.GetWidth()) / img.GetHeight()
               if imgAspect > 1:
                  height = self.imageListBitmapSize / imgAspect
                  img.Rescale(self.imageListBitmapSize, height)
                  img.Resize(wx.Size(self.imageListBitmapSize, self.imageListBitmapSize), wx.Point(0, (self.imageListBitmapSize-height)/2))
               else:
                  width = self.imageListBitmapSize * imgAspect
                  img.Rescale(width, self.imageListBitmapSize)
                  img.Resize(wx.Size(self.imageListBitmapSize, self.imageListBitmapSize), wx.Point((self.imageListBitmapSize-width)/2))
               bitmap = wx.BitmapFromImage(img)
               self.imageList.Add(bitmap)
               self.imagePathList.append(imgFile)
               self.imageDimensionList.append(dimension)

      self.scriptView.ClearAll()

      self.scriptView.SetImageList(self.imageList, wx.IMAGE_LIST_SMALL)

      self.scriptView.InsertColumn(0, "image")

      # populate scriptView
      for i,line in enumerate(script):
         line = line.strip()
         imgFile = getImageFromScriptLine(line)
         if imgFile:
            info = wx.ListItem()
            info.SetId(i)
            info.SetMask(wx.LIST_MASK_IMAGE ) #| wx.LIST_MASK_TEXT)
            info.SetImage(self.imagePathList.index(imgFile))
            #info.SetText(':'.join(line.split(':')[1:]))
            self.scriptView.InsertItem(info)
         else:
            info = wx.ListItem()
            info.SetId(i)
            info.SetMask(wx.LIST_MASK_TEXT)
            #info.SetText(line)
            self.scriptView.InsertItem(info)

      self.scriptView.SetColumnWidth(0, 1000)



   def loadDirectory(self, path):
      # populate image list and path
      for infile in glob.glob(os.path.join(path,'*.jpg') ): # this must match the for infile line below otherwise you'll get an 'item not in list error'  #'*.jpg', '*.JPG') ):
         imgFile = infile 
         img = wx.Image(imgFile)
         dimension = (img.GetWidth(), img.GetHeight())
         imgAspect = float(img.GetWidth()) / img.GetHeight()
         if imgAspect > 1:
            height = self.imageListBitmapSize / imgAspect
            img.Rescale(self.imageListBitmapSize, height)
            img.Resize(wx.Size(self.imageListBitmapSize, self.imageListBitmapSize), wx.Point(0, (self.imageListBitmapSize-height)/2))
#            img.Rotate90(True)         
         else:
            width = self.imageListBitmapSize * imgAspect
            img.Rescale(width, self.imageListBitmapSize)
            img.Resize(wx.Size(self.imageListBitmapSize, self.imageListBitmapSize), wx.Point((self.imageListBitmapSize-width)/2))

#         bitmap = wx.BitmapFromImage(img.Rotate90(False) ) #thumbnail image
         bitmap = wx.BitmapFromImage(img) #thumbnail image
         self.imageList.Add(bitmap)#thumbnail image
         self.imagePathList.append(imgFile)
         self.imageDimensionList.append(dimension)
            
         self.scriptView.ClearAll()

      self.scriptView.SetImageList(self.imageList, wx.IMAGE_LIST_SMALL)

      self.scriptView.InsertColumn(0, "image")

      # populate scriptView
      for infile in glob.glob(os.path.join(path, '*.jpg') ): # the join statement is just like in SQL and it filters for only .jpg files
         imgFile = infile
         if imgFile:
            info = wx.ListItem()
            #info.SetId(i)
            info.SetMask(wx.LIST_MASK_IMAGE | wx.LIST_MASK_TEXT)
            info.SetImage(self.imagePathList.index(imgFile))
            #info.SetText(infile)
            self.scriptView.InsertItem(info)
         else:
            info = wx.ListItem()
            #info.SetId(i)
            info.SetMask(wx.LIST_MASK_TEXT)
            #info.SetText(infile)
            self.scriptView.InsertItem(info)

      self.scriptView.SetColumnWidth(0, 1000)

   def onScriptViewDrag(self, event):
      data = wx.TextDataObject()
      fromIndex = event.GetIndex()
      data.SetText(str(fromIndex))

      self.dropIndex = 'waiting' # indicate that we're waiting for drop

      ds = wx.DropSource(self.scriptView)
      ds.SetData(data)
      result = ds.DoDragDrop(flags = wx.Drag_DefaultMove)

      if (result == wx.DragMove) and (fromIndex != self.dropIndex):
         debug('dragndrop: %d to %d' % (fromIndex, self.dropIndex))
         self.setUnsavedChanges(True)
         allItems = [self.scriptView.GetItem(i) for i in range(0, self.scriptView.GetItemCount())]
         originalLength = len(allItems)

         # first pull out all selected items from allItems
         allSelected = []
         i = 0
         while i < len(allItems):
            if allItems[i].m_state & wx.LIST_STATE_SELECTED:
               allSelected.append(allItems[i])
               del allItems[i]
               if i < self.dropIndex:
                  self.dropIndex -= 1
            else:
               i += 1

         # next, insert the selected items back at self.dropIndex location
         result = allItems[:(min(len(allItems), self.dropIndex))] + allSelected
         if self.dropIndex < len(allItems):
            result.extend(allItems[self.dropIndex:])

         assert originalLength == len(result), "Aiiee!! drag'n'drop resulted in a change in length!"

         for i in range(len(result)):
            result[i].m_itemId = i
            itemState = result[i].m_state
            self.scriptView.SetItem(result[i])
            self.scriptView.SetItemState(i, itemState, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
            self.imagePanel.displayScriptLine('') # clear imagePanel since I don't know which line is the focus now

   def onDrop(self, x, y, text):
      index,flags = self.scriptView.HitTest((x,y))

      if index == wx.NOT_FOUND:
         if flags & wx.List_HITTEST_NOWHERE:
            index = self.scriptView.GetItemCount()
         else:
            return

      if self.dropIndex == 'waiting': # make sure we're the source of the drag
         self.dropIndex = index
      else:
         return

   def onPictControlSelectionDragged(self, event):
      self.setUnsavedChanges(True)
      item = self.scriptView.GetItem(self.currentFocused)

      lineElems = item.GetText().split(':')
      params = lineElems[3].split(';')
      params[event.box*2] = event.param.split(';')[0]
      params[event.box*2+1] = event.param.split(';')[1]
      lineElems[3] = ';'.join(params)

      item.SetText(':'.join(lineElems))
      self.scriptView.SetItem(item) # modify the display

   def onLineFocused(self, event):
      self.currentFocused = event.m_itemIndex
      debug('currentFocused: %d' % self.currentFocused)
      self.imagePanel.displayScriptLine(self.constructScriptLine(self.currentFocused))

   def onLineEdited(self, event):
      self.setUnsavedChanges(True)
      self.currentFocused = event.m_itemIndex

      item = self.scriptView.GetItem(self.currentFocused)
      imageIndex = item.GetImage()

      # update pict control
      if imageIndex != -1:
         self.imagePanel.displayScriptLine('%s:%s' % (self.imagePathList[imageIndex], event.GetLabel()))
      else:
         self.imagePanel.displayScriptLine(event.GetLabel())

   def onScriptRightClick(self, event):
      self.PopupMenu(self.popupMenu)

   def onAddKenburns(self, event):
      def getRandomAroundAnchor(rrange, ranchor):
         return random.randrange(rrange) - (rrange/2) + ranchor

      cFrameSizePercentRange = 18 # range of percentage the randomizer is going to use. Even number only please
      cFramePosPercentRange = 14 # range of percentage the randomizer is going to use. Even number only please

      self.setUnsavedChanges(True)

      # go through all selected items in the list and add kenburns if:
      # * the item contains image
      # * the item does not already contain an effect
      for i in range(self.scriptView.GetItemCount()):
         item = self.scriptView.GetItem(i)
         if (item.m_state & wx.LIST_STATE_SELECTED) and (item.GetImage() != -1) and (len(item.GetText().split(':')) < 3):
            # alright, we're adding kenburns on this item
            # find the percentage of either imagewidth or imageheight that we will use for this image
            pictIndex = item.GetImage()
            imgAspect = float(self.imageDimensionList[pictIndex][0]) / self.imageDimensionList[pictIndex][1]
            desiredAspect = (4.0/3, 16.0/9)[bool(self.options.widescreen)]
            if imgAspect < desiredAspect:
               sizeAnchor = int(float(self.imageDimensionList[pictIndex][0]) * 100 / (self.imageDimensionList[pictIndex][1] * desiredAspect))
            else:
               sizeAnchor = int(float(self.imageDimensionList[pictIndex][1]) * 100 / (self.imageDimensionList[pictIndex][0] / desiredAspect))

            # we're going to randomize cFrameSizePercentRange around the sizeAnchor. So the sizeAnchor must be adjusted.
            sizeAnchor = min(sizeAnchor, (100-(cFrameSizePercentRange/2))-5)

            randomSizes = []
            randomSizes.append(getRandomAroundAnchor(cFrameSizePercentRange, sizeAnchor))
            # 25 % of the time we're going to only pan, the rest, pan and zoom
            if random.randrange(4) == 3:
               randomSizes.append(randomSizes[0])  # pan only
            else:
               randomSizes.append(getRandomAroundAnchor(cFrameSizePercentRange, sizeAnchor)) # pan and zoom

            lineElems = item.GetText().split(':')
            if len(lineElems) == 1:
               lineElems.append('') # append empty elem for subtitle
            lineElems.append('kenburns')
            lineElems.append('%d%%;%d%%,%d%%;%d%%;%d%%,%d%%' % (randomSizes[0],
                                                               getRandomAroundAnchor(cFramePosPercentRange, 50),
                                                               getRandomAroundAnchor(cFramePosPercentRange, 50),
                                                               randomSizes[1],
                                                               getRandomAroundAnchor(cFramePosPercentRange, 50),
                                                               getRandomAroundAnchor(cFramePosPercentRange, 50)))

            item.SetText(':'.join(lineElems))
            self.scriptView.SetItem(item)

   def onAddCrop(self, event):
      self.setUnsavedChanges(True)

      # go through all selected items in the list and add crop if:
      # * the item contains image
      # * the item does not already contain an effect
      for i in range(self.scriptView.GetItemCount()):
         item = self.scriptView.GetItem(i)
         if (item.m_state & wx.LIST_STATE_SELECTED) and (item.GetImage() != -1) and (len(item.GetText().split(':')) < 3):
            lineElems = item.GetText().split(':')
            if len(lineElems) == 1:
               lineElems.append('') # append empty elem for subtitle
            lineElems.append('crop')
            lineElems.append('90%;middle') # we're just going to use 90% crop in the middle. No point randomizing since we're most probably be wrong.
            item.SetText(':'.join(lineElems))
            self.scriptView.SetItem(item)

   def onDelEffect(self, event):
      self.setUnsavedChanges(True)

      # go through all selected items in the list and remove effect if
      # * the item contains image
      for i in range(self.scriptView.GetItemCount()):
         item = self.scriptView.GetItem(i)
         if (item.m_state & wx.LIST_STATE_SELECTED) and (item.GetImage() != -1):
            lineElems = item.GetText().split(':')
            del lineElems[2:]
            item.SetText(':'.join(lineElems))
            self.scriptView.SetItem(item)

   def onEdit(self, event):
      self.scriptView.EditLabel(self.currentFocused)

   def onUseEditor(self, event):
      self.setUnsavedChanges(True)

      if not hasattr(self, 'tempdir'):
         self.tempdir = tempfile.mkdtemp(prefix='slideshow-editor-tmp')
         debug('created tempdir: %s' % self.tempdir)

      tempFile = os.path.join(self.tempdir, os.path.basename(self.scriptPath))
      debug('generating tempfile: %s' % tempFile)
      with open(tempFile, 'w') as f:
         f.writelines([self.constructScriptLine(i)+'\n' for i in range(self.scriptView.GetItemCount())])

      debug('Execute: %s %s' % ('xdg-open', tempFile))
      subprocess.call(['xdg-open', tempFile])

      dlg = wx.MessageDialog(self, "When you finish editing, please click OK", "Waiting for edit", wx.OK | wx.ICON_INFORMATION)
      dlg.ShowModal()
      dlg.Destroy()

      with open(tempFile) as f:
         script = f.readlines()
      self.loadScript(script)

      os.unlink(tempFile)

   def execute_dvd_slideshow(self, args, dir):
      # launch dvd-slideshow. The simplest way to do this that I can think
      # of is executing this inside a new terminal, but which terminal to use?

      if subprocess.call(['which', 'gnome-terminal']) == 0:
         cmd = ['gnome-terminal', '-x', 'dvd-slideshow'] + args
      elif subprocess.call(['which', 'konsole']) == 0:
         cmd = ['konsole', '-x', 'dvd-slideshow'] + args
      else:
         dlg = wx.MessageDialog(self, "Failed to find a terminal to use.\nPlease install gnome-terminal or konsole.", "Can't find terminal", wx.OK | wx.ICON_ERROR)
         dlg.ShowModal()
         dlg.Destroy()
         return

      debug('launching: %s' % cmd)
      retcode = subprocess.call(cmd, cwd=dir)
      time.sleep(1) # don't know why this is needed. Otherwise the terminal doesn't get launched

   def onPreview(self, event):
      debug( event.GetId() == ID_POPUP_HQPREVIEW)

      # detect if we have mplayer
      if subprocess.call(['which', 'mplayer']) != 0:
         dlg = wx.MessageDialog(self, "Failed to find mplayer for the preview.\nPlease install mplayer to use this feature", "Can't find mplayer", wx.OK | wx.ICON_ERROR)
         dlg.ShowModal()
         dlg.Destroy()
         return

      if not hasattr(self, 'tempdir'):
         self.tempdir = tempfile.mkdtemp(prefix='slideshow-editor-tmp')
         debug('created tempdir: %s' % self.tempdir)

      tempFile = os.path.join(self.tempdir, os.path.basename(self.scriptPath))
      debug('generating tempfile: %s' % tempFile)

      with open(tempFile, 'w') as f:
         f.writelines([self.constructScriptLine(i)+'\n' for i in range(self.scriptView.GetItemCount()) if self.scriptView.GetItemState(i, wx.LIST_STATE_SELECTED)])

      self.execute_dvd_slideshow([('-L', '-H')[event.GetId() == ID_POPUP_HQPREVIEW], '-f', tempFile], self.tempdir)

      # now call mplayer to view it
      dlg = wx.MessageDialog(self, "Please click OK when dvd-slideshow is done", "Waiting for dvd-slideshow", wx.OK | wx.ICON_INFORMATION)
      isPreviewAgain = dlg.ShowModal()
      dlg.Destroy()
      while isPreviewAgain == wx.ID_OK:
         subprocess.call(['mplayer', '-sid', '0', '-nofs', '%s.vob' % (os.path.splitext(tempFile)[0])])
         dlg = wx.MessageDialog(self, "Preview again?", "Preview again", wx.OK | wx.CANCEL | wx.ICON_QUESTION)
         isPreviewAgain = dlg.ShowModal()
         dlg.Destroy()

   def onGenerateSlideshow(self, event):
      if self.isUnsavedChanges:
         dlg = wx.MessageDialog(self, "Script is not saved. Please save it first before generating slideshow.", "Unsaved changes detected", wx.OK | wx.ICON_ERROR)
         dlg.ShowModal()
         dlg.Destroy()
         return

      self.execute_dvd_slideshow(['-H', '-f', self.scriptPath], os.path.dirname(self.scriptPath))
      time.sleep(5) # don't know why this is needed. Otherwise the terminal doesn't get launched
      dlg = wx.MessageDialog(self, "Please click OK when dvd-slideshow is done", "Waiting for dvd-slideshow", wx.OK | wx.ICON_INFORMATION)
      dlg.ShowModal()
      dlg.Destroy()

   def onUsage(self, event):
      info = wx.AboutDialogInfo()
      info.Name = ProgName
      info.Version = ProgVersion
      info.Copyright = "(C) 2010 dvd-slideshow-editor's contributors"
      info.Description = wordwrap(
            "A GUI editor for dvd-slideshow script.\n\nUsage:\n\n"
            "Left pane contains the raw script. You can edit this directly, and your change will be reflected on the right pane\n\n"
            "Right pane contains the sample picture and the effect bounding box. You can move and resize the box(es). By default, this will use keyword snap. Hold down alt for no snap. Hold down ctrl and alt for no snap and no aspect ratio\n",
            350, wx.ClientDC(self))

      info.WebSite = ("http://code.google.com/p/dvd-slideshow-editor/", "dvd-slideshow-editor project page")

      info.License = "http://www.gnu.org/licenses/gpl.html"

      # Then we call wx.AboutBox giving it that info object
      wx.AboutBox(info)

   # TODO
   #def onAddPicts(self, event):
   #   self.setUnsavedChanges(True)
   #   pass
   #def onAddSongs(self, event):
   #   self.setUnsavedChanges(True)
   #   pass
   #def onEditPreferences(self, event):
   #   pass

def parseOptions(argv):
   """
   Given parse command line, return a tuple containing the options selected by user
   """
   # build option parser
   optParser = optparse.OptionParser(prog = ProgName, description = "GUI editor for dvd-slideshow script", usage = "usage: %prog [options] [dvd-slideshow-script]")
   optParser.add_option("-w", "--widescreen", action = "store_true", help = "widescreen (16:9). Default: 4.3")
   optParser.add_option("-v", "--verbose", action = "store_true", help = "verbose prints for debugging")

   # parse arguments and validate. Exit if not valid
   (options,extraArgs) = optParser.parse_args(argv)

   if len(extraArgs) == 2:
      scriptPath = extraArgs[1]
   elif len(extraArgs) == 1:
      scriptPath = None #os.getcwd()
   else:
      optParser.print_help()
      sys.exit(1)

   return (options, scriptPath)


def main(argv = None):
   """
   The main program
   returns 0 for success, non-zero for failure
   """
   if argv is None:
      argv = sys.argv

   (options, scriptPath) = parseOptions(argv)

   if options.verbose:
      logLevel = logging.DEBUG
   else:
      logLevel = logging.INFO
   logging.basicConfig(level = logLevel,
                        format='%(asctime)s %(message)s',
                        datefmt='%d %b %Y %H:%M:%S')

   random.seed()

   app = wx.PySimpleApp()
   frame = MainWindow(None, wx.ID_ANY, "photo-print-prep", options, scriptPath)
   app.MainLoop()

   return 0

### execute main if this module run as opposed to imported ###
if __name__ == "__main__":
   sys.exit(main())
