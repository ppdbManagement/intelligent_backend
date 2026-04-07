import json
import os
import traceback
import uuid
from django.http import JsonResponse
from django.views import View
from utils.responseContentUtil import *
from ..models import Document
from django.db.models import Q
from django.core.paginator import Paginator
from ..serializers.parseTotalStatusSerializers import ParseTotalStatusListSerializer
from config.backendSettings import MEDIA_ROOT



