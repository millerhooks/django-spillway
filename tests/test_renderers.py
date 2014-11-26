import sys
import io
import json
import zipfile

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import Paginator
from django.test import SimpleTestCase, TestCase
from rest_framework.pagination import PaginationSerializer
from PIL import Image

from spillway import renderers
from spillway.collections import Feature, FeatureCollection
from .models import Location, _geom
from .test_models import RasterTestBase, RasterStoreTestBase


class GeoJSONRendererTestCase(SimpleTestCase):
    def setUp(self):
        self.data = Feature(id=1, properties={'name': 'San Francisco'},
                            geometry=_geom)
        self.collection = FeatureCollection(features=[self.data])
        self.r = renderers.GeoJSONRenderer()

    def test_render_feature(self):
        data = json.loads(self.r.render(self.data))
        self.assertEqual(data, self.data)
        self.assertEqual(self.r.render({}), str(Feature()))

    def test_render_feature_collection(self):
        data = json.loads(self.r.render(self.collection))
        self.assertEqual(data, self.collection)
        self.assertEqual(self.r.render([]), str(FeatureCollection()))


class KMLRendererTestCase(SimpleTestCase):
    def setUp(self):
        self.data = {'id': 1,
                     'properties': {'name': 'playground',
                                    'notes': 'epic slide'},
                     'geometry': GEOSGeometry(json.dumps(_geom)).kml}

    def test_render(self):
        rkml = renderers.KMLRenderer()
        self.assertIn(self.data['geometry'], rkml.render(self.data))

    def test_render_kmz(self):
        rkmz = renderers.KMZRenderer()
        stream = io.BytesIO(rkmz.render(self.data))
        self.assertTrue(zipfile.is_zipfile(stream))
        zf = zipfile.ZipFile(stream)
        self.assertIn(self.data['geometry'], zf.read('doc.kml'))


class SVGRendererTestCase(TestCase):
    def setUp(self):
        Location.create()
        self.qs = Location.objects.svg()
        self.svg = self.qs[0].svg
        self.data = {'id': 1,
                     'properties': {'name': 'playground',
                                    'notes': 'epic slide'},
                     'geometry': self.svg}

    def test_render(self):
        rsvg = renderers.SVGRenderer()
        svgdoc = rsvg.render(self.data)
        self.assertIn(self.data['geometry'], svgdoc)

        #serializer = FeatureSerializer(self.qs)
        ##serializer.opts.model = self.qs.model
        #svgdoc = rsvg.render(serializer.data)
        #print svgdoc
        #self.assertIn(self.data['geometry'], svgdoc)


class RasterRendererTestCase(RasterTestBase):
    img_header = 'EHFA_HEADER_TAG'

    def test_render_geotiff(self):
        f = renderers.GeoTIFFRenderer().render(self.data)
        self.assertEqual(f.filelike.read(), self.f.read())

    def test_render_imagine(self):
        data = renderers.HFARenderer().render(self.data)
        # Read the image header.
        self.assertEqual(data.filelike[:15], self.img_header)

    def test_render_hfazip(self):
        f = renderers.HFAZipRenderer().render(self.data)
        zf = zipfile.ZipFile(f.filelike)
        self.assertTrue(all(name.endswith('.img') for name in zf.namelist()))
        self.assertEqual(zf.read(zf.namelist()[0])[:15], self.img_header)

    def test_render_tifzip(self):
        tifs = [self.data, self.data]
        f = renderers.GeoTIFFZipRenderer().render(tifs)
        zf = zipfile.ZipFile(f.filelike)
        self.assertEqual(len(zf.filelist), len(tifs))
        self.assertTrue(all(name.endswith('.tif') for name in zf.namelist()))


class MapnikRendererTestCase(RasterStoreTestBase):
    def test_render(self):
        ctx = {'bbox': self.object.geom}
        imgdata = renderers.MapnikRenderer().render(
            self.object, renderer_context=ctx)
        im = Image.open(io.BytesIO(imgdata))
        self.assertEqual(im.size, (256, 256))
        self.assertNotEqual(im.getpixel((100, 100)), (0, 0, 0, 0))

    def test_compat(self):
        from spillway import compat
        sys.modules.pop('mapnik')
        sys.path = []
        reload(compat)
        with self.assertRaises(ImproperlyConfigured):
            m = compat.mapnik.Map(128, 128)
