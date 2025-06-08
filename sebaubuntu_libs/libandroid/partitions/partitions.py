#
# Copyright (C) 2022 Sebastiano Barezzi
#
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import Dict

from sebaubuntu_libs.libandroid.partitions.partition import AndroidPartition, BUILD_PROP_LOCATION
from sebaubuntu_libs.libandroid.partitions.partition_model import SSI, TREBLE, PartitionModel

def get_extended_search_locations(base_path: Path, partition_name: str):
	"""
	Obtener ubicaciones extendidas para buscar build.prop según las rutas mencionadas:
	- dump_path/system/system/build.prop
	- dump_path/vendor/build.prop  
	- dump_path/vendor_boot/ramdisk/default.prop
	- dump_path/vendor_boot/ramdisk/build.prop
	"""
	locations = []
	
	# Ubicaciones estándar
	standard_locations = [
		base_path / partition_name,
		base_path / partition_name / partition_name,  # Para system/system
	]
	
	# Ubicaciones específicas basadas en el contexto de extracción
	if partition_name == "system":
		extended_locations = [
			# Ubicaciones estándar de system
			base_path / "system",
			base_path / "system" / "system", 
			
			# Ubicaciones en dumps de imágenes extraídas
			base_path / "boot" / "ramdisk" / "system",
			base_path / "recovery" / "ramdisk" / "system",
			base_path / "vendor_boot" / "ramdisk" / "system",
			
			# Ubicaciones en AIK extraído
			base_path.parent / "ramdisk" / "system",
			base_path.parent / "vendor_ramdisk" / "system",
		]
	elif partition_name == "vendor":
		extended_locations = [
			# Ubicaciones estándar de vendor
			base_path / "vendor",
			
			# Ubicaciones en dumps de imágenes extraídas  
			base_path / "boot" / "ramdisk" / "vendor",
			base_path / "recovery" / "ramdisk" / "vendor", 
			base_path / "vendor_boot" / "ramdisk" / "vendor",
			
			# Ubicaciones en AIK extraído
			base_path.parent / "ramdisk" / "vendor",
			base_path.parent / "vendor_ramdisk" / "vendor",
		]
	else:
		# Para otras particiones, usar ubicaciones estándar
		extended_locations = standard_locations
		
	locations.extend(extended_locations)
	
	# Ubicaciones adicionales globales para cualquier partición
	global_locations = [
		# Directorio raíz del dump
		base_path / partition_name,
		
		# Dentro de estructuras de extracción de imágenes
		base_path / "boot" / "ramdisk" / partition_name,
		base_path / "recovery" / "ramdisk" / partition_name,
		base_path / "vendor_boot" / "ramdisk" / partition_name,
		
		# Directorios padre (para casos donde estamos en un subdirectorio)
		base_path.parent / partition_name,
		base_path.parent / "ramdisk" / partition_name,
		base_path.parent / "vendor_ramdisk" / partition_name,
		base_path.parent.parent / partition_name,
	]
	
	locations.extend(global_locations)
	
	# Remover duplicados manteniendo el orden
	seen = set()
	unique_locations = []
	for loc in locations:
		if loc not in seen:
			seen.add(loc)
			unique_locations.append(loc)
			
	return unique_locations

def get_extended_build_prop_locations():
	"""
	Obtener ubicaciones extendidas de build.prop incluyendo:
	- default.prop y prop.default para vendor_boot/ramdisk
	- Todas las variantes estándar de build.prop
	"""
	extended_locations = [
		# Archivos estándar de propiedades
		"build.prop",
		"default.prop", 
		"prop.default",
		
		# Ubicaciones en subdirectorios
		"etc/build.prop",
		"system/build.prop",
		"vendor/build.prop",
		"product/build.prop",
		"system_ext/build.prop",
		"odm/build.prop",
	]
	
	return [Path(loc) for loc in extended_locations]

class Partitions:
	def __init__(self, dump_path: Path):
		self.dump_path = dump_path

		self.partitions: Dict[PartitionModel, AndroidPartition] = {}

		# Search for system con ubicaciones extendidas
		system_found = False
		system_search_locations = get_extended_search_locations(self.dump_path, "system")
		extended_build_prop_locations = get_extended_build_prop_locations()
		
		for system_location in system_search_locations:
			if system_found:
				break
				
			# Buscar tanto en BUILD_PROP_LOCATION estándar como en ubicaciones extendidas
			all_prop_locations = list(BUILD_PROP_LOCATION) + extended_build_prop_locations
			
			for build_prop_location in all_prop_locations:
				prop_file = system_location / build_prop_location
				if prop_file.is_file():
					self.partitions[PartitionModel.SYSTEM] = AndroidPartition(PartitionModel.SYSTEM, system_location)
					system_found = True
					break

		assert PartitionModel.SYSTEM in self.partitions, f"System partition not found. Searched in: {[str(loc) for loc in system_search_locations]}"
		self.system = self.partitions[PartitionModel.SYSTEM]

		# Search for vendor con ubicaciones extendidas
		vendor_found = False
		vendor_search_locations = get_extended_search_locations(self.dump_path, "vendor")
		
		# Añadir la ubicación estándar dentro de system
		vendor_search_locations.insert(0, self.partitions[PartitionModel.SYSTEM].path / "vendor")
		
		for vendor_location in vendor_search_locations:
			if vendor_found:
				break
				
			for build_prop_location in all_prop_locations:
				prop_file = vendor_location / build_prop_location
				if prop_file.is_file():
					self.partitions[PartitionModel.VENDOR] = AndroidPartition(PartitionModel.VENDOR, vendor_location)
					vendor_found = True
					break

		assert PartitionModel.VENDOR in self.partitions, f"Vendor partition not found. Searched in: {[str(loc) for loc in vendor_search_locations]}"
		self.vendor = self.partitions[PartitionModel.VENDOR]

		# Search for the other partitions con búsqueda extendida
		for model in [model for model in PartitionModel.from_group(SSI) if not (model is PartitionModel.SYSTEM)]:
			self._search_for_partition_extended(model)

		for model in [model for model in PartitionModel.from_group(TREBLE) if not (model is PartitionModel.VENDOR)]:
			self._search_for_partition_extended(model)

	def get_partition(self, model: PartitionModel):
		if not model:
			return None

		if model in self.partitions:
			return self.partitions[model]

		return None

	def get_partition_by_name(self, name: str):
		return self.get_partition(PartitionModel.from_name(name))

	def get_all_partitions(self):
		return self.partitions.values()

	def _search_for_partition_extended(self, model: PartitionModel):
		"""Búsqueda extendida para particiones usando las nuevas ubicaciones."""
		extended_build_prop_locations = get_extended_build_prop_locations()
		all_prop_locations = list(BUILD_PROP_LOCATION) + extended_build_prop_locations
		
		# Ubicaciones posibles extendidas
		possible_locations = get_extended_search_locations(self.dump_path, model.name)
		
		# Añadir ubicaciones estándar
		possible_locations.extend([
			self.partitions[PartitionModel.SYSTEM].path / model.name,
			self.partitions[PartitionModel.VENDOR].path / model.name,
			self.dump_path / model.name
		])

		for location in possible_locations:
			if model in self.partitions:
				break
				
			for build_prop_location in all_prop_locations:
				prop_file = location / build_prop_location
				if prop_file.is_file():
					self.partitions[model] = AndroidPartition(model, location)
					break

	def _search_for_partition(self, model: PartitionModel):
		"""Método de búsqueda original mantenido para compatibilidad."""
		possible_locations = [
			self.partitions[PartitionModel.SYSTEM].path / model.name,
			self.partitions[PartitionModel.VENDOR].path / model.name,
			self.dump_path / model.name
		]

		for location in possible_locations:
			for build_prop_location in BUILD_PROP_LOCATION:
				if not (location / build_prop_location).is_file():
					continue

				self.partitions[model] = AndroidPartition(model, location)
				break
