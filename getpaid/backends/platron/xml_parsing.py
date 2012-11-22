class ResponseTemplate:
    def __init__(self):
        self.xml = {}
        self.end_tag = ''
        self.additional = False
        self.additional_data = ''

    def start(self, tag, attrib):
        if tag != 'response':
            if tag == 'pg_ps_additional_data':
                self.additional = True

            if self.additional:
                self.additional_data += '<%s>' % tag
            self.end_tag = tag

    def end(self, tag):
        if tag != 'response':
            self.end_tag = ''
        if self.additional:
            self.additional_data += '</%s>' % tag

    def data(self, data):
        if self.additional:
            self.additional_data += data
        else:
            self.xml[self.end_tag] = data

    def close(self):
        if self.additional_data:
            self.xml['pg_ps_additional_data'] = self.additional_data
        return self.xml


class RequestTemplate:
    def __init__(self):
        self.xml = {}
        self.record = False
        self.end_tag = ''

    def start(self, tag, attrib):
        if tag == 'request':
            self.record = True
        else:
            self.end_tag = tag

    def end(self, tag):
        if tag == 'request':
            self.record = False
        else:
            self.end_tag = ''

    def data(self, data):
        if self.record and self.end_tag:
            self.xml[self.end_tag] = data

    def close(self):
        return self.xml
