# -*- coding: utf-8 -*-

""" LabView RSRC file format data fill.

    Implements storage of data which maps to types defined within VI.
"""

# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.


import enum
import struct

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from ctypes import *

from LVmisc import *
import LVxml as ET
import LVclasses
import LVdatatype
import LVdatatyperef


class DataFill:
    def __init__(self, vi, tdType, tdSubType, po):
        """ Creates new DataFill object, capable of handling generic data.
        """
        self.vi = vi
        self.po = po
        self.tdType = tdType
        self.tdSubType = tdSubType
        self.index = -1
        self.tm_flags = None
        self.td = None
        self.value = None

    def isRefnumTag(self, td):
        """ Returns if given refnum td is a tag type.
        """
        from LVdatatyperef import REFNUM_TYPE
        if td.refType() in (REFNUM_TYPE.IVIRef,REFNUM_TYPE.VisaRef,\
          REFNUM_TYPE.UsrDefTagFlt,REFNUM_TYPE.UsrDefndTag,):
            return True
        return False

    def isSpecialDSTMClusterElement(self, idx, tm_flags):
        ver = self.vi.getFileVersion()

        if (tm_flags & 0x0004) != 0:
            if isSmallerVersion(ver, 10,0,0,2):
                if idx == 2:
                    return True
            else:
                if idx == 1:
                    return True
            return False
        if (tm_flags & 0x0010) != 0:
            if idx in (1,2,3,):
                return True
        elif (tm_flags & 0x0020) != 0:
            if idx == 3:
                return True
        elif (tm_flags & 0x0040) != 0:
            if idx == 2:
                return True
        return False

    def setTD(self, td, idx, tm_flags = 0):
        if self.tdType != td.fullType():
            raise RuntimeError("Class {} type {} cannot be linked to TD type {}"\
              .format(type(self).__name__, self.getXMLTagName(),\
               enumOrIntToName(td.fullType()) ))
        if (self.po.verbose > 2):
            print("{:s}: {:s} {:d}: Setting TD {}"\
              .format(self.vi.src_fname, type(self).__name__, self.index, td))
        self.index = idx
        self.td = td
        self.tm_flags = tm_flags

    def prepareDict(self):
        typeName = enumOrIntToName(self.tdType)
        return { 'type': typeName, 'value': self.value }

    def __repr__(self):
        d = self.prepareDict()
        from pprint import pformat
        return type(self).__name__ + pformat(d, indent=0, compact=True, width=512)

    def getXMLTagName(self):
        from LVdatatype import TD_FULL_TYPE, tdEnToName, mdFlavorEnToName
        from LVdatatyperef import refnumEnToName
        if self.tdType == TD_FULL_TYPE.MeasureData:
            tagName = mdFlavorEnToName(self.tdSubType)
        elif self.tdType == TD_FULL_TYPE.Refnum:
            tagName = refnumEnToName(self.tdSubType)
        else:
            tagName = tdEnToName(self.tdType)
        return tagName

    def initWithRSRC(self, bldata):
        self.initWithRSRCParse(bldata)
        if (self.po.verbose > 2):
            print("{:s}: {} offs after {}"\
              .format(self.vi.src_fname,str(self),bldata.tell()))
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        """ Returns part of the Data Fill re-created from properties.

        To be overloaded in classes for specific Data Fill types.
        """
        data_buf = b''
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = None
        return exp_whole_len

    def initWithXML(self, df_elem):
        """ Early part of Data Fill loading from XML file

        At the point it is executed, other sections are inaccessible.
        To be overriden by child classes which want to load more properties from XML.
        """
        pass

    def initWithXMLLate(self):
        """ Late part of Data Fill loading from XML file

        Can access some basic data from other blocks and sections.
        Useful only if properties needs an update after other blocks are accessible.
        """
        pass

    def exportXML(self, df_elem, fname_base):
        #self.parseData() # no need, as we never store default fill in raw form
        pass


class DataFillVoid(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = None

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        return exp_whole_len

    def initWithXML(self, df_elem):
        pass

    def exportXML(self, df_elem, fname_base):
        pass


class DataFillInt(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.base = 10
        from LVdatatype import TD_FULL_TYPE
        if self.tdType in (TD_FULL_TYPE.NumInt8,):
            self.size = 1
            self.signed = True
        elif self.tdType in (TD_FULL_TYPE.NumInt16,):
            self.size = 2
            self.signed = True
        elif self.tdType in (TD_FULL_TYPE.NumInt32,):
            self.size = 4
            self.signed = True
        elif self.tdType in (TD_FULL_TYPE.NumInt64,):
            self.size = 8
            self.signed = True
        elif self.tdType in (TD_FULL_TYPE.NumUInt8,):
            self.size = 1
            self.signed = False
        elif self.tdType in (TD_FULL_TYPE.NumUInt16,):
            self.size = 2
            self.signed = False
        elif self.tdType in (TD_FULL_TYPE.NumUInt32,):
            self.size = 4
            self.signed = False
        elif self.tdType in (TD_FULL_TYPE.NumUInt64,):
            self.size = 8
            self.signed = False
        elif self.tdType in (TD_FULL_TYPE.UnitUInt8,):
            self.size = 1
            self.signed = False
        elif self.tdType in (TD_FULL_TYPE.UnitUInt16,):
            self.size = 2
            self.signed = False
        elif self.tdType in (TD_FULL_TYPE.UnitUInt32,):
            self.size = 4
            self.signed = False
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))

    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(self.size), byteorder='big', signed=self.signed)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = int(self.value).to_bytes(self.size, byteorder='big', signed=self.signed)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = self.size
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)


class DataFillFloat(DataFill):
    def initWithRSRCParse(self, bldata):
        from LVdatatype import TD_FULL_TYPE
        if self.tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
            self.value = struct.unpack('>f', bldata.read(4))[0]
        elif self.tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
            self.value = struct.unpack('>d', bldata.read(8))[0]
        elif self.tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
            self.value = readQuadFloat(bldata)
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        from LVdatatype import TD_FULL_TYPE
        if self.tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
            data_buf += struct.pack('>f', self.value)
        elif self.tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
            data_buf += struct.pack('>d', self.value)
        elif self.tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
            data_buf += prepareQuadFloat(self.value)
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        from LVdatatype import TD_FULL_TYPE
        if self.tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
            exp_whole_len += 4
        elif self.tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
            exp_whole_len += 8
        elif self.tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
            exp_whole_len += 16
        else:
            exp_whole_len = None
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = float(df_elem.text)
        pass

    def exportXML(self, df_elem, fname_base):
        # Precision of 128-bit float is circa 71 digits
        df_elem.text = "{:.71g}".format(self.value)
        pass


class DataFillComplex(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.value = (None,None,)

    def initWithRSRCParse(self, bldata):
        from LVdatatype import TD_FULL_TYPE
        if self.tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,):
            self.value = struct.unpack('>ff', bldata.read(8))
        elif self.tdType in (TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,):
            self.value = struct.unpack('>dd', bldata.read(16))
        elif self.tdType in (TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
            self.value = (readQuadFloat(bldata),readQuadFloat(bldata),)
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        from LVdatatype import TD_FULL_TYPE
        if self.tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,):
            data_buf += struct.pack('>ff', self.value[0], self.value[1])
        elif self.tdType in (TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,):
            data_buf += struct.pack('>dd', self.value[0], self.value[1])
        elif self.tdType in (TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
            data_buf += prepareQuadFloat(self.value[0])
            data_buf += prepareQuadFloat(self.value[1])
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        from LVdatatype import TD_FULL_TYPE
        if self.tdType in (TD_FULL_TYPE.NumComplex64,TD_FULL_TYPE.UnitComplex64,):
            exp_whole_len += 8
        elif self.tdType in (TD_FULL_TYPE.NumComplex128,TD_FULL_TYPE.UnitComplex128,):
            exp_whole_len += 16
        elif self.tdType in (TD_FULL_TYPE.NumComplexExt,TD_FULL_TYPE.UnitComplexExt,):
            exp_whole_len += 32
        else:
            exp_whole_len = None
        return exp_whole_len

    def initWithXML(self, df_elem):
        valRe = float(df_elem.find('real').text)
        valIm = float(df_elem.find('imag').text)
        self.value = (valRe,valIm,)
        pass

    def exportXML(self, df_elem, fname_base):
        tags = ('real', 'imag',)
        for i, val in enumerate(self.value):
            subelem = ET.SubElement(df_elem, tags[i])
            subelem.text = "{:.71g}".format(val)
        pass


class DataFillBool(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.size = None

    def initVersion(self):
        """ Initialization part which requires access to version
        """
        from LVdatatype import TD_FULL_TYPE
        if self.tdType in (TD_FULL_TYPE.BooleanU16,):
            self.size = 2
        elif self.tdType in (TD_FULL_TYPE.Boolean,):
            ver = self.vi.getFileVersion()
            if isGreaterOrEqVersion(ver, 4,5,0):
                self.size = 1
            else:
                self.size = 2
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))
        pass

    def initWithRSRCParse(self, bldata):
        self.initVersion()
        self.value = int.from_bytes(bldata.read(self.size), byteorder='big', signed=False)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.value).to_bytes(self.size, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        exp_whole_len += self.size
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)

    def initWithXMLLate(self):
        super().initWithXMLLate()
        self.initVersion()

    def exportXML(self, df_elem, fname_base):
        df_elem.text = str(self.value)


class DataFillString(DataFill):
    def initWithRSRCParse(self, bldata):
        strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        #if self.td.prop1 != 0xffffffff: # in such case part of the value might be irrelevant, as only
        # part to the size (self.td.prop1 & 0x7fffffff) is used; but the length stored is still valid
        self.value = bldata.read(strlen)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += len(self.value).to_bytes(4, byteorder='big', signed=False)
        data_buf += self.value
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        exp_whole_len += 4 + len(self.value)
        return exp_whole_len

    def initWithXML(self, df_elem):
        if df_elem.text is not None: # Empty string may be None after parsing
            elem_text = ET.unescape_safe_store_element_text(df_elem.text)
            self.value = elem_text.encode(self.vi.textEncoding)
        else:
            self.value = b''
        pass

    def exportXML(self, df_elem, fname_base):
        elemText = self.value.decode(self.vi.textEncoding)
        ET.safe_store_element_text(df_elem, elemText)


class DataFillPath(DataFill):
    def initWithRSRCParse(self, bldata):
        startPos = bldata.tell()
        clsident = bldata.read(4)
        if clsident == b'PTH0':
            self.value = LVclasses.LVPath0(self.vi, self.po)
        elif clsident in (b'PTH1', b'PTH2',):
            self.value = LVclasses.LVPath1(self.vi, self.po)
        else:
            raise RuntimeError("Data fill {} contains path data of unrecognized class {}"\
              .format(self.getXMLTagName(),clsident))
        bldata.seek(startPos)
        self.value.parseRSRCData(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += self.value.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = self.value.expectedRSRCSize()
        return exp_whole_len

    def initWithXML(self, df_elem):
        clsident = df_elem.get("Ident")
        if clsident == 'PTH0':
            self.value = LVclasses.LVPath0(self.vi, self.po)
        elif clsident in ('PTH1', 'PTH2',):
            self.value = LVclasses.LVPath1(self.vi, self.po)
        else:
            raise RuntimeError("Data fill {} contains path data of unrecognized class {}"\
          .format(self.getXMLTagName(),clsident))
        self.value.initWithXML(df_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        self.value.initWithXMLLate()

    def exportXML(self, df_elem, fname_base):
        self.value.exportXML(df_elem, fname_base)
        pass


class DataFillCString(DataFill):
    def initWithRSRCParse(self, bldata):
        # No idea why sonething which looks like string type stores 32-bit value instead
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.value).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillArray(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.value = []
        self.dimensions = []

    def prepareDict(self):
        d = super().prepareDict()
        d.update( { 'dimensions': self.dimensions } )
        return d

    def setTD(self, td, idx, tm_flags = 0):
        super().setTD(td, idx, tm_flags)
        if len(self.value) < 1:
            return # If value list is not filled yet, no further work to do
        # We expect exactly one client within Array
        for cli_idx, td_idx, td_obj, td_flags in self.td.clientsEnumerate():
                sub_td = td_obj
        for sub_df in self.value:
            sub_df.setTD(sub_td, -1, self.tm_flags)

    def initWithRSRCParse(self, bldata):
        self.dimensions = []
        for dim in self.td.dimensions:
            val = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.dimensions.append(val)
        if len(self.td.clients) < 1:
            raise RuntimeError("TD {} used for DataFill before being initialized".format(enumOrIntToName(self.td.fullType())))
        # Multiply sizes of each dimension to get total number of items
        totItems = 1
        # TODO the amounts are in self.dimensions; maybe they need to be same as self.td.dimensions, unless dynamic size is used? print warning?
        for dim in self.dimensions:
            totItems *= dim & 0x7fffffff
        self.value = []
        # We expect exactly one client within Array
        for cli_idx, td_idx, td_obj, td_flags in self.td.clientsEnumerate():
                sub_td = td_obj
                sub_td_idx = td_idx
        #if sub_td.fullType() in (TD_FULL_TYPE.Boolean,) and isSmallerVersion(ver, 4,5,0,1): # TODO expecting special case, never seen it though
        if totItems > self.po.array_data_limit:
                raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
                  .format(self.getXMLTagName(), totItems, self.po.array_data_limit))
        for i in range(totItems):
            try:
                sub_df = newDataFillObjectWithTD(self.vi, sub_td_idx, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(sub_td.fullType()), str(e)))
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for dim in self.dimensions:
            data_buf += int(dim).to_bytes(4, byteorder='big', signed=False)
        for sub_df in self.value:
            data_buf += sub_df.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        exp_whole_len += 4 * len(self.dimensions)
        for sub_df in self.value:
            sub_len = sub_df.expectedRSRCSize()
            if sub_len is None:
                return None
            exp_whole_len += sub_len
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.dimensions = []
        self.value = []
        for i, subelem in enumerate(df_elem):
            if (subelem.tag == 'dim'):
                val = int(subelem.text, 0)
                self.dimensions.append(val)
                continue
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for sub_df in self.value:
            sub_df.initWithXMLLate()

    def exportXML(self, df_elem, fname_base):
        for dim in self.dimensions:
            subelem = ET.SubElement(df_elem, 'dim')
            subelem.text = "{:d}".format(dim)
        for sub_df in self.value:
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class DataFillArrayDataPtr(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.value).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillCluster(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.value = []

    def setTD(self, td, idx, tm_flags = 0):
        super().setTD(td, idx, tm_flags)
        if len(self.value) < 1:
            return # If value list is not filled yet, no further work to do
        for cli_idx, td_idx, sub_td, td_flags in self.td.clientsEnumerate():
            sub_df = self.value[cli_idx]
            sub_df.setTD(sub_td, td_idx, self.tm_flags)

    def initWithRSRCParse(self, bldata):
        self.value = []
        for cli_idx, td_idx, sub_td, td_flags in self.td.clientsEnumerate():
            try:
                sub_df = newDataFillObjectWithTD(self.vi, td_idx, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(sub_td.fullType()), str(e)))
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for sub_df in self.value:
            data_buf += sub_df.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        for sub_df in self.value:
            sub_len = sub_df.expectedRSRCSize()
            if sub_len is None:
                return None
            exp_whole_len += sub_len
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = []
        for i, subelem in enumerate(df_elem):
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for sub_df in self.value:
            sub_df.initWithXMLLate()

    def exportXML(self, df_elem, fname_base):
        for sub_df in self.value:
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class DataFillLVVariant(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.useConsolidatedTypes = True

    def initWithRSRCParse(self, bldata):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 6,0,0,2):
            self.value = LVclasses.LVVariant(0, self.vi, self.po, useConsolidatedTypes=self.useConsolidatedTypes, allowFillValue=True)
        else:
            self.value = LVclasses.OleVariant(0, self.vi, self.po)
        self.value.parseRSRCData(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += self.value.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = self.value.expectedRSRCSize()
        return exp_whole_len

    def initWithXML(self, df_elem):
        if df_elem.tag == LVclasses.LVVariant.__name__:
            self.value = LVclasses.LVVariant(0, self.vi, self.po, useConsolidatedTypes=self.useConsolidatedTypes, allowFillValue=True)
        elif df_elem.tag == LVclasses.OleVariant.__name__:
            self.value = LVclasses.OleVariant(0, self.vi, self.po)
        else:
            raise AttributeError("Class {} encountered unexpected tag '{}'".format(type(self).__name__, df_elem.tag))
        self.value.initWithXML(df_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        self.value.initWithXMLLate()

    def exportXML(self, df_elem, fname_base):
        self.value.exportXML(df_elem, fname_base)


class DataFillMeasureData(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.containedTd = None

    def initVersion(self):
        """ Initialization part which requires access to version
        """
        ver = self.vi.getFileVersion()
        from LVdatatype import MEASURE_DATA_FLAVOR, TD_FULL_TYPE, newTDObject,\
          newDigitalTableCluster, newDigitalWaveformCluster, newDynamicTableCluster,\
          newAnalogWaveformCluster, newOldFloat64WaveformCluster

        if isSmallerVersion(ver, 7,0,0,2):
            raise NotImplementedError("MeasureData {} default value read is not implemented for versions below LV7"\
              .format(enumOrIntToName(sub_td.dtFlavor())))

        if self.tdSubType in (MEASURE_DATA_FLAVOR.OldFloat64Waveform,):
            self.containedTd = newOldFloat64WaveformCluster(self.vi, -1, 0, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Int16Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumInt16, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Float64Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumFloat64, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Float32Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumFloat32, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.TimeStamp,):
            # Use block of 16 bytes as Timestamp
            self.containedTd = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.Block, self.po)
            self.containedTd.blkSize = 16
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Digitaldata,):
            self.containedTd = newDigitalTableCluster(self.vi, -1, 0, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.DigitalWaveform,):
            self.containedTd = newDigitalWaveformCluster(self.vi, -1, 0, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Dynamicdata,):
            self.containedTd = newDynamicTableCluster(self.vi, -1, 0, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.FloatExtWaveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumFloatExt, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.UInt8Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumUInt8, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.UInt16Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumUInt16, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.UInt32Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumUInt32, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Int8Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumInt8, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Int32Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumInt32, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Complex64Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumComplex64, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Complex128Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumComplex128, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.ComplexExtWaveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumComplexExt, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Int64Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumInt64, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.UInt64Waveform,):
            tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumUInt64, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        else:
            raise NotImplementedError("MeasureData {} default value read failed due to unsupported flavor"\
              .format(self.getXMLTagName()))
        pass

    def setTD(self, td, idx, tm_flags = 0):
        super().setTD(td, idx, tm_flags)
        # Do not propagate to clients - self.containedTd should be propagated
        # And it is propagates somewhere else

    def prepareDict(self):
        flavorName = enumOrIntToName(self.tdSubType)
        d = super().prepareDict()
        d.update( { 'flavor': flavorName } )
        return d

    def initWithRSRCParse(self, bldata):
        self.initVersion()
        self.value = []
        try:
            sub_df = newDataFillObjectWithTD(self.vi, -1, self.tm_flags, self.containedTd, self.po)
            self.value.append(sub_df)
            sub_df.initWithRSRC(bldata)
        except Exception as e:
            raise RuntimeError("MeasureData flavor {}: {}"\
              .format(enumOrIntToName(self.containedTd.fullType()), str(e)))
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for sub_df in self.value:
            data_buf += sub_df.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        for sub_df in self.value:
            sub_len = sub_df.expectedRSRCSize()
            if sub_len is None:
                return None
            exp_whole_len += sub_len
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = []
        for i, subelem in enumerate(df_elem):
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        self.initVersion()
        self.containedTd.initWithXMLLate()
        for sub_df in self.value:
            sub_df.setTD(self.containedTd, -1, self.tm_flags)
        for sub_df in self.value:
            sub_df.initWithXMLLate()

    def exportXML(self, df_elem, fname_base):
        for i, sub_df in enumerate(self.value):
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class DataFillComplexFixedPt(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.value = 2 * [None]
        self.vflags = 2 * [None]

    def prepareDict(self):
        d = super().prepareDict()
        d.update( { 'vflags': self.vflags } )
        return d

    def initWithRSRCParse(self, bldata):
        # Not sure about the order of values in this type
        self.value = 2 * [None]
        self.vflags = 2 * [None]
        for i in range(2):
            self.value[i] = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
            if self.td.allocOv:
                self.vflags[i] = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for i in range(2):
            data_buf += int(self.value[i]).to_bytes(8, byteorder='big', signed=False)
            if self.td.allocOv:
                data_buf += int(self.vflags[i]).to_bytes(1, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        for i in range(2):
            exp_whole_len += 8
            if self.td.allocOv:
                exp_whole_len += 1
        return exp_whole_len

    def initWithXML(self, df_elem):
        subelem = df_elem.find('real')
        valRe = int(subelem.text, 0)
        flagRe = subelem.get("Flags")
        if flagRe is not None:
            flagRe = int(flagRe, 0)
        subelem = df_elem.find('imag')
        valIm = int(subelem.text, 0)
        flagIm = subelem.get("Flags")
        if flagIm is not None:
            flagIm = int(flagIm, 0)
        self.value = [valRe,valIm,]
        self.vflags = [flagRe,flagIm,]
        pass

    def exportXML(self, df_elem, fname_base):
        tags = ("real", "imag",)
        for i, val in enumerate(self.value):
            subelem = ET.SubElement(df_elem, tags[i])
            subelem.text = "{:d}".format(val)
            subelem.set("Flags", "0x{:02X}".format(self.vflags[i]))
        pass


class DataFillFixedPoint(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.vflags = None

    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
        if self.td.allocOv:
            self.vflags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        else:
            self.vflags = None

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.value).to_bytes(8, byteorder='big', signed=False)
        if self.td.allocOv:
            data_buf += int(self.vflags).to_bytes(1, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        if True:
            exp_whole_len += 8
            if self.td.allocOv:
                exp_whole_len += 1
        return exp_whole_len

    def initWithXML(self, df_elem):
        valRe = int(df_elem.text, 0)
        flagRe = df_elem.get("Flags")
        if flagRe is not None:
            flagRe = int(flagRe, 0)
        self.value = valRe
        self.vflags = flagRe
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        if self.vflags is not None:
            df_elem.set("Flags", "0x{:02X}".format(self.vflags))
        pass


class DataFillBlock(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = bldata.read(self.td.blkSize)

    def prepareRSRCData(self, avoid_recompute=False):
        if len(self.value) != self.td.blkSize:
            eprint("{:s}: Length of value ({}) is different than expected block size ({})"\
              .format(self.vi.src_fname, len(self.value), self.td.blkSize))
            padding_len = self.td.blkSize - len(self.value)
            if padding_len > 0:
                self.value += (padding_len * b'\0')
            else:
                self.value = self.value[:self.td.blkSize]
        data_buf = b''
        data_buf += self.value
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        exp_whole_len += len(self.value)
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = bytes.fromhex(df_elem.text)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = self.value.hex()
        pass


class DataFillRepeatedBlock(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.value = []

    def setTD(self, td, idx, tm_flags = 0):
        super().setTD(td, idx, tm_flags)
        if len(self.value) < 1:
            return # If value list is not filled yet, no further work to do
        for cli_idx, td_idx, td_obj, td_flags in self.td.clientsEnumerate():
                sub_td = td_obj
                sub_td_idx = td_idx
        for sub_df in self.value:
            sub_df.setTD(sub_td, sub_td_idx, self.tm_flags)

    def initWithRSRCParse(self, bldata):
        self.value = []
        VCTP = self.vi.get_or_raise('VCTP')
        for cli_idx, td_idx, td_obj, td_flags in self.td.clientsEnumerate():
                sub_td = td_obj
                sub_td_idx = td_idx
        if self.td.numRepeats > self.po.array_data_limit:
            raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
              .format(self.getXMLTagName(), self.td.numRepeats, self.po.array_data_limit))
        for i in range(self.td.numRepeats):
            try:
                sub_df = newDataFillObjectWithTD(self.vi, sub_td_idx, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(sub_td.fullType()), str(e)))
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for sub_df in self.value:
            data_buf += sub_df.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        for sub_df in self.value:
            sub_len = sub_df.expectedRSRCSize()
            if sub_len is None:
                return None
            exp_whole_len += sub_len
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = []
        for i, subelem in enumerate(df_elem):
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for sub_df in self.value:
            sub_df.initWithXMLLate()

    def exportXML(self, df_elem, fname_base):
        comments = {}
        if self.td is not None:
            comments = self.td.dfComments
        for i, sub_df in enumerate(self.value):
            if (i in comments) and (comments[i] != ""):
                comment_elem = ET.Comment(" {:s} ".format(comments[i]))
                df_elem.append(comment_elem)
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class DataFillSimpleRefnum(DataFill):
    """ Data Fill for Simple Refnum types.

    Used for "normal" ref types, which only contain 4 byte value.
    """
    def prepareDict(self):
        refName = enumOrIntToName(self.tdSubType)
        d = super().prepareDict()
        d.update( { 'refType': refName } )
        return d

    def initWithRSRCParse(self, bldata):
        # The format seem to be different for LV6.0.0 and older, but still 4 bytes
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.value).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillIORefnum(DataFill):
    """ Data Fill for IORefnum types.

    Used for ref types which represent IORefnum.
    """
    def prepareDict(self):
        refName = enumOrIntToName(self.tdSubType)
        d = super().prepareDict()
        d.update( { 'refType': refName } )
        return d

    def initWithRSRCParse(self, bldata):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 6,0,0):
            if self.isRefnumTag(self.td):
                strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.value = bldata.read(strlen)
            else:
                self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        else:
            self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 6,0,0):
            if self.isRefnumTag(self.td):
                data_buf += len(self.value).to_bytes(4, byteorder='big', signed=False)
                data_buf += self.value
            else:
                data_buf += int(self.value).to_bytes(4, byteorder='big', signed=False)
        else:
            data_buf += int(self.value).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 0
        if isGreaterOrEqVersion(ver, 6,0,0):
            if self.isRefnumTag(self.td):
                data_buf += 4 + len(self.value)
            else:
                exp_whole_len += 4
        else:
            exp_whole_len += 4
        return exp_whole_len

    def initWithXML(self, df_elem):
        storedAs = df_elem.get("StoredAs")
        if storedAs == "String":
            if df_elem.text is not None: # Empty string may be None after parsing
                elem_text = ET.unescape_safe_store_element_text(df_elem.text)
                self.value = elem_text.encode(self.vi.textEncoding)
            else:
                self.value = b''
        elif storedAs == "Int":
            self.value = int(df_elem.text, 0)
        else:
            raise AttributeError("Class {} encountered unexpected StoredAs value '{}'".format(type(self).__name__, storedAs))
        pass

    def exportXML(self, df_elem, fname_base):
        if isinstance(self.value, (bytes, bytearray,)):
            elemText = self.value.decode(self.vi.textEncoding)
            ET.safe_store_element_text(df_elem, elemText)
            df_elem.set("StoredAs", "String")
        else:
            df_elem.text = "{:d}".format(self.value)
            df_elem.set("StoredAs", "Int")
        pass


class DataFillUDRefnum(DataFill):
    """ Data Fill for non-tag UDRefnum types.

    Used for ref types which represent Non-tag subtypes of UDRefnum.
    """
    def prepareDict(self):
        refName = enumOrIntToName(self.tdSubType)
        d = super().prepareDict()
        d.update( { 'refType': refName } )
        return d

    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.value).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillUDTagRefnum(DataFill):
    """ Data Fill for tag UDRefnum types.

    Used for ref types which represent Tag subtypes of UDRefnum.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.usrdef1 = None
        self.usrdef2 = None
        self.usrdef3 = None
        self.usrdef4 = None

    def prepareDict(self):
        d = super().prepareDict()
        d.update( { 'usrdef1': self.usrdef1, 'usrdef2': self.usrdef2, 'usrdef3': self.usrdef3, 'usrdef4': self.usrdef4 } )
        return d

    def initWithRSRCParse(self, bldata):
        from LVdatatyperef import REFNUM_TYPE
        ver = self.vi.getFileVersion()
        self.usrdef1 = None
        self.usrdef2 = None
        self.usrdef3 = None
        self.usrdef4 = None
        strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.value = bldata.read(strlen)
        if isGreaterOrEqVersion(ver, 12,0,0,2) and isSmallerVersion(ver, 12,0,0,5):
            bldata.read(1)
        if self.td.refType() in (REFNUM_TYPE.UsrDefTagFlt,):
            strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.usrdef1 = bldata.read(strlen)
            strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.usrdef2 = bldata.read(strlen)
            self.usrdef3 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.usrdef4 = bldata.read(strlen)

    def prepareRSRCData(self, avoid_recompute=False):
        from LVdatatyperef import REFNUM_TYPE
        ver = self.vi.getFileVersion()
        data_buf = b''
        data_buf += len(self.value).to_bytes(4, byteorder='big', signed=False)
        data_buf += self.value
        if isGreaterOrEqVersion(ver, 12,0,0,2) and isSmallerVersion(ver, 12,0,0,5):
            data_buf += b'\0'
        if self.td.refType() in (REFNUM_TYPE.UsrDefTagFlt,):
            data_buf += len(self.usrdef1).to_bytes(4, byteorder='big', signed=False)
            data_buf += self.usrdef1
            data_buf += len(self.usrdef2).to_bytes(4, byteorder='big', signed=False)
            data_buf += self.usrdef2
            data_buf += len(self.usrdef3).to_bytes(4, byteorder='big', signed=False)
            data_buf += len(self.usrdef4).to_bytes(4, byteorder='big', signed=False)
            data_buf += self.usrdef4
        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 0
        exp_whole_len += 4 + len(self.value)
        if isGreaterOrEqVersion(ver, 12,0,0,2) and isSmallerVersion(ver, 12,0,0,5):
            exp_whole_len += 1
        if self.td.refType() in (REFNUM_TYPE.UsrDefTagFlt,):
            exp_whole_len += 4 + len(self.usrdef1)
            exp_whole_len += 4 + len(self.usrdef2)
            exp_whole_len += 4
            exp_whole_len += 4 + len(self.usrdef4)
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.usrdef1 = None
        self.usrdef2 = None
        self.usrdef3 = None
        self.usrdef4 = None
        if df_elem.text is not None: # Empty string may be None after parsing
            elem_text = ET.unescape_safe_store_element_text(df_elem.text)
            self.value = elem_text.encode(self.vi.textEncoding)
        else:
            self.value = b''
        usrdef = df_elem.get("UsrDef1")
        if usrdef is not None:
            self.usrdef1 = usrdef.encode(self.vi.textEncoding)
        usrdef = df_elem.get("UsrDef2")
        if usrdef is not None:
            self.usrdef2 = usrdef.encode(self.vi.textEncoding)
        usrdef = df_elem.get("UsrDef3")
        if usrdef is not None:
            self.usrdef3 = int(usrdef, 0)
        usrdef = df_elem.get("UsrDef4")
        if usrdef is not None:
            self.usrdef4 = usrdef.encode(self.vi.textEncoding)
        pass

    def exportXML(self, df_elem, fname_base):
        elemText = self.value.decode(self.vi.textEncoding)
        ET.safe_store_element_text(df_elem, elemText)
        if self.usrdef1 is not None:
            df_elem.set("UsrDef1", self.usrdef1.decode(self.vi.textEncoding))
        if self.usrdef2 is not None:
            df_elem.set("UsrDef2", self.usrdef2.decode(self.vi.textEncoding))
        if self.usrdef3 is not None:
            df_elem.set("UsrDef3", "{:d}".format(self.usrdef3))
        if self.usrdef4 is not None:
            df_elem.set("UsrDef4", self.usrdef4.decode(self.vi.textEncoding))
        pass


class DataFillUDClassInst(DataFill):
    """ Data Fill for UDClassInst Refnum types.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.value = []
        self.libName = b''

    def initWithRSRCParse(self, bldata):
        self.value = []
        numLevels = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.libName = bldata.read(strlen)
        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes
        if numLevels > self.po.typedesc_list_limit:
            raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
              .format(self.getXMLTagName(), numLevels, self.po.typedesc_list_limit))
        for i in range(numLevels):
            datalen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            libVersion = bldata.read(datalen)
            self.value.append(libVersion)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += len(self.value).to_bytes(4, byteorder='big', signed=False)
        data_buf += preparePStr(self.libName, 4, self.po)
        for libVersion in self.value:
            data_buf += len(libVersion).to_bytes(4, byteorder='big', signed=False)
            data_buf += libVersion
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        exp_whole_len += 4
        if True:
            str_len += 1 + len(self.libName)
            uneven_len = str_len % 4
            if uneven_len > 0:
                str_len += 4 - uneven_len
            exp_whole_len += str_len
        for libVersion in self.value:
            exp_whole_len += 4 + len(libVersion)
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = []
        self.libName = b''
        for i, subelem in enumerate(df_elem):
            if subelem.tag == "LibName":
                if subelem.text is not None: # Empty string may be None after parsing
                    val_text = ET.unescape_safe_store_element_text(subelem.text)
                    val = val_text.encode(self.vi.textEncoding)
                else:
                    val = b''
                self.libName = val
            elif subelem.tag == "LibVersion":
                if subelem.text is not None: # Empty string may be None after parsing
                    val_text = ET.unescape_safe_store_element_text(subelem.text)
                    val = val_text.encode(self.vi.textEncoding)
                else:
                    val = b''
                self.value.append(val)
            else:
                raise AttributeError("Class {} encountered unexpected tag '{}'".format(type(self).__name__, subelem.tag))
        pass

    def exportXML(self, df_elem, fname_base):
        if True:
            subelem = ET.SubElement(df_elem, "LibName")
            elemText = self.libName.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, elemText)
        for i, libVersion in enumerate(self.value):
            subelem = ET.SubElement(df_elem, "LibVersion")
            elemText = libVersion.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, elemText)
        pass


class DataFillPtr(DataFill):
    def initWithRSRCParse(self, bldata):
        ver = self.vi.getFileVersion()
        if isSmallerVersion(ver, 8,6,0,1):
            self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        else:
            self.value = None

    def prepareRSRCData(self, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''
        if isSmallerVersion(ver, 8,6,0,1):
            data_buf += int(self.value).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 0
        if isSmallerVersion(ver, 8,6,0,1):
            exp_whole_len += 4
        return exp_whole_len

    def initWithXML(self, df_elem):
        if df_elem.text != "None":
            self.value = int(df_elem.text, 0)
        else:
            self.value = None
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{}".format(self.value)
        pass


class DataFillPtrTo(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.value).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillExtData(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = None # TODO implement reading ExtData
        raise NotImplementedError("ExtData default value read is not implemented")

    def initWithXML(self, df_elem):
        raise NotImplementedError("ExtData default value read is not implemented")


class DataFillUnexpected(DataFill):
    """ Data fill for types for which we never expect this call, but it may be ignored

    Types which reference this class would cause silently ignored error in LV14.
    """
    def initWithRSRCParse(self, bldata):
        self.value = None
        eprint("{:s}: Warning: Data fill asks to read default value of {} type, this should never happen."\
          .format(self.vi.src_fname, self.getXMLTagName()))

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = None
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = None
        eprint("{:s}: Warning: Data fill parsing found default value of {} type, this should never happen."\
          .format(self.vi.src_fname, self.getXMLTagName()))
        pass

    def exportXML(self, df_elem, fname_base):
        pass


class DataFillTypeDef(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.value = []

    def setTD(self, td, idx, tm_flags = 0):
        super().setTD(td, idx, tm_flags)
        if len(self.value) < 1:
            return # If value list is not filled yet, no further work to do
        # We expect exactly one client within TypeDef
        for cli_idx, td_idx, td_obj, td_flags in self.td.clientsEnumerate():
            sub_td = td_obj
        for sub_df in self.value:
            sub_df.setTD(sub_td, -1, self.tm_flags)

    def initWithRSRCParse(self, bldata):
        self.value = []
        # We expect exactly one client within TypeDef
        for cli_idx, td_idx, sub_td, td_flags in self.td.clientsEnumerate():
            try:
                sub_df = newDataFillObjectWithTD(self.vi, -1, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(client.nested.fullType()), str(e)))
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for sub_df in self.value:
            data_buf += sub_df.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 0
        for sub_df in self.value:
            sub_len = sub_df.expectedRSRCSize()
            if sub_len is None:
                return None
            exp_whole_len += sub_len
        return exp_whole_len

    def initWithXML(self, df_elem):
        self.value = []
        for i, subelem in enumerate(df_elem):
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for sub_df in self.value:
            sub_df.initWithXMLLate()

    def exportXML(self, df_elem, fname_base):
        for sub_df in self.value:
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class SpecialDSTMCluster(DataFillCluster):
    def getXMLTagName(self):
        return "SpecialDSTMCluster"

    def setTD(self, td, idx, tm_flags = 0):
        DataFill.setTD(self, td, idx, tm_flags)
        if len(self.value) < 1:
            return # If value list is not filled yet, no further work to do
        skipNextEntry = ((self.tm_flags & 0x0200) != 0)
        cli_idx = 0
        for cli_bad_idx, td_idx, sub_td, td_flags in self.td.clientsEnumerate():
            if not self.isSpecialDSTMClusterElement(cli_idx, self.tm_flags):
                continue
            if skipNextEntry:
                skipNextEntry = False
                continue
            sub_df = self.value[cli_idx]
            cli_idx += 1
            sub_df.setTD(sub_td, td_idx, self.tm_flags)
        pass

    def initWithRSRCParse(self, bldata):
        self.value = []
        skipNextEntry = ((self.tm_flags & 0x0200) != 0)
        for cli_idx, td_idx, sub_td, td_flags in self.td.clientsEnumerate():
            if not self.isSpecialDSTMClusterElement(cli_idx, self.tm_flags):
                continue
            if skipNextEntry:
                skipNextEntry = False
                continue
            try:
                sub_df = newDataFillObjectWithTD(self.vi, td_idx, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(sub_td.fullType()), str(e)))
            pass
        pass

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for sub_df in self.value:
            data_buf += sub_df.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf



def newSpecialDSTMClusterWithTD(vi, idx, tm_flags, td, po):
    """ Creates and returns new data fill object with given parameters
    """
    from LVdatatype import TD_FULL_TYPE
    tdType = td.fullType()
    tdSubType = None
    df = SpecialDSTMCluster(vi, tdType, tdSubType, po)
    df.setTD(td, idx, tm_flags)
    return df

def newDataFillRefnum(vi, tdType, tdSubType, po):
    """ Creates and returns new data fill object for refnum with given parameters
    """
    from LVdatatyperef import REFNUM_TYPE
    refType = tdSubType
    ctor = {
        REFNUM_TYPE.IVIRef: DataFillIORefnum,
        REFNUM_TYPE.VisaRef: DataFillIORefnum,
        REFNUM_TYPE.Imaq: DataFillIORefnum,
        REFNUM_TYPE.UsrDefTagFlt: DataFillUDTagRefnum,
        REFNUM_TYPE.UsrDefndTag: DataFillUDTagRefnum,
        REFNUM_TYPE.UsrDefined: DataFillUDRefnum,
        REFNUM_TYPE.UDClassInst: DataFillUDClassInst,
    }.get(refType, DataFillSimpleRefnum)
    if ctor is None:
        raise RuntimeError("Data type Refnum kind {}: No known way to read default data"\
          .format(enumOrIntToName(refType),str(e)))
    return ctor(vi, tdType, tdSubType, po)


def newDataFillObject(vi, tdType, tdSubType, po):
    """ Creates and returns new data fill object with given parameters
    """
    from LVdatatype import TD_FULL_TYPE
    ctor = {
        TD_FULL_TYPE.Void: DataFillVoid,
        TD_FULL_TYPE.NumInt8: DataFillInt,
        TD_FULL_TYPE.NumInt16: DataFillInt,
        TD_FULL_TYPE.NumInt32: DataFillInt,
        TD_FULL_TYPE.NumInt64: DataFillInt,
        TD_FULL_TYPE.NumUInt8: DataFillInt,
        TD_FULL_TYPE.NumUInt16: DataFillInt,
        TD_FULL_TYPE.NumUInt32: DataFillInt,
        TD_FULL_TYPE.NumUInt64: DataFillInt,
        TD_FULL_TYPE.NumFloat32: DataFillFloat,
        TD_FULL_TYPE.NumFloat64: DataFillFloat,
        TD_FULL_TYPE.NumFloatExt: DataFillFloat,
        TD_FULL_TYPE.NumComplex64: DataFillComplex,
        TD_FULL_TYPE.NumComplex128: DataFillComplex,
        TD_FULL_TYPE.NumComplexExt: DataFillComplex,
        TD_FULL_TYPE.UnitUInt8: DataFillInt,
        TD_FULL_TYPE.UnitUInt16: DataFillInt,
        TD_FULL_TYPE.UnitUInt32: DataFillInt,
        TD_FULL_TYPE.UnitFloat32: DataFillFloat,
        TD_FULL_TYPE.UnitFloat64: DataFillFloat,
        TD_FULL_TYPE.UnitFloatExt: DataFillFloat,
        TD_FULL_TYPE.UnitComplex64: DataFillComplex,
        TD_FULL_TYPE.UnitComplex128: DataFillComplex,
        TD_FULL_TYPE.UnitComplexExt: DataFillComplex,
        TD_FULL_TYPE.BooleanU16: DataFillBool,
        TD_FULL_TYPE.Boolean: DataFillBool,
        TD_FULL_TYPE.String: DataFillString,
        TD_FULL_TYPE.Path: DataFillPath,
        TD_FULL_TYPE.Picture: DataFillString,
        TD_FULL_TYPE.CString: DataFillCString,
        TD_FULL_TYPE.PasString: DataFillCString,
        TD_FULL_TYPE.Tag: DataFillString,
        TD_FULL_TYPE.SubString: DataFillUnexpected,
        TD_FULL_TYPE.Array: DataFillArray,
        TD_FULL_TYPE.ArrayDataPtr: DataFillArrayDataPtr,
        TD_FULL_TYPE.SubArray: DataFillUnexpected,
        TD_FULL_TYPE.ArrayInterfc: DataFillArray,
        TD_FULL_TYPE.Cluster: DataFillCluster,
        TD_FULL_TYPE.LVVariant: DataFillLVVariant,
        TD_FULL_TYPE.MeasureData: DataFillMeasureData,
        TD_FULL_TYPE.ComplexFixedPt: DataFillComplexFixedPt,
        TD_FULL_TYPE.FixedPoint: DataFillFixedPoint,
        TD_FULL_TYPE.Block: DataFillBlock,
        TD_FULL_TYPE.TypeBlock: DataFillTypeDef,
        TD_FULL_TYPE.VoidBlock: DataFillVoid,
        TD_FULL_TYPE.AlignedBlock: DataFillBlock,
        TD_FULL_TYPE.RepeatedBlock: DataFillRepeatedBlock,
        TD_FULL_TYPE.AlignmntMarker: DataFillVoid,
        TD_FULL_TYPE.Refnum: newDataFillRefnum,
        TD_FULL_TYPE.Ptr: DataFillPtr,
        TD_FULL_TYPE.PtrTo: DataFillPtrTo,
        TD_FULL_TYPE.ExtData: DataFillExtData,
        TD_FULL_TYPE.Function: DataFillUnexpected,
        TD_FULL_TYPE.TypeDef: DataFillTypeDef,
        TD_FULL_TYPE.PolyVI: DataFillUnexpected,
    }.get(tdType, None)
    if ctor is None:
        raise RuntimeError("Data type {}: No known way to read default data"\
          .format(enumOrIntToName(tdType),str(e)))
    return ctor(vi, tdType, tdSubType, po)

def newDataFillObjectWithTD(vi, idx, tm_flags, td, po):
    """ Creates and returns new data fill object with given parameters
    """
    from LVdatatype import TD_FULL_TYPE
    tdType = td.fullType()
    if tdType == TD_FULL_TYPE.MeasureData:
        tdSubType = td.dtFlavor()
    elif tdType == TD_FULL_TYPE.Refnum:
        tdSubType = td.refType()
    else:
        tdSubType = None
    df = newDataFillObject(vi, tdType, tdSubType, po)
    df.setTD(td, idx, tm_flags)
    return df

def newDataFillObjectWithTag(vi, tagName, po):
    """ Creates and returns new data fill object from given XML tag name
    """
    from LVdatatype import TD_FULL_TYPE, tdNameToEnum, mdFlavorNameToEnum
    from LVdatatyperef import refnumNameToEnum
    tdType = tdNameToEnum(tagName)
    if tdType is None:
        raise AttributeError("Data Fill creation encountered unexpected tag '{}'".format(tagName))
    if tdType == TD_FULL_TYPE.MeasureData:
        tdSubType = LVdatatype.mdFlavorNameToEnum(tagName)
    elif tdType == TD_FULL_TYPE.Refnum:
        tdSubType = refnumNameToEnum(tagName)
    else:
        tdSubType = None
    df = newDataFillObject(vi, tdType, tdSubType, po)
    return df
