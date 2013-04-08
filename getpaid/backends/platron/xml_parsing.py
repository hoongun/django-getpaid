from xml.dom.minidom import parseString


class XMLParser(object):
    def __init__(self, max_depth=2):
        self.max_depth = max_depth
        self.depth = 0

    def parse(self, xml_node):
        d = {}
        self.depth += 1
        for node in xml_node.childNodes:
            if node.nodeType != node.TEXT_NODE:
                d[node.tagName] = ''
                if node.childNodes:
                    textnode = node.childNodes[0]
                    if textnode.nodeType == node.TEXT_NODE and len(node.childNodes) == 1:
                        d[node.tagName] = textnode.nodeValue
                    elif self.depth <= self.max_depth:
                        d[node.tagName] = self.parse(node)
                    else:
                        print textnode
        self.depth -= 1
        return d

    @classmethod
    def to_dict(cls, xml, max_depth=2):
        parser = cls(max_depth)

        xml = parseString(unicode(xml).encode('utf-8'))
        request = xml.getElementsByTagName('request')
        response = xml.getElementsByTagName('response')

        if response:
            return parser.parse(response[0])
        elif request:
            return parser.parse(request[0])
        else:
            return {}

    @staticmethod
    def to_xml(elements, type='request'):
        params = ''
        for key, value in elements.items():
            params += '  <%(key)s>%(value)s</%(key)s>\n' % {'key': key, 'value': value}

        xml = '<?xml version="1.0" encoding="utf-8"?>'\
                '<%(type)s>\n%(params)s</%(type)s>' % {'type': type, 'params': params}
        return unicode(xml).encode('utf-8')
