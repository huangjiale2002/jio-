import os
import tqdm
import numpy as np
from PIL import Image
import re



Vaihingen_COLOR_MAP = [
    [255, 255, 255],  # 不透水路面 Impervious surfaces (RGB: 255, 255, 255)
    [0, 0, 255],  # 建筑物 Building (RGB: 0, 0, 255)
    [0, 255, 255],  # 低植被 Low vegetation (RGB: 0, 255, 255)
    [0, 255, 0],  # 树木 Tree (RGB: 0, 255, 0)
    [255, 255, 0],  # 汽车 Car (RGB: 255, 255, 0)
    [255, 0, 0]  # 背景 Clutter/background (RGB: 255, 0, 0)
]


def DSM2RGB(dsm_array, colormap='viridis'):
    """
    将DSM数组转换为RGB可视化图像
    
    Args:
        dsm_array: DSM数组 (numpy array)
        colormap: 颜色映射方案 ( 'jet', 'terrain')
    
    Returns:
        RGB图像数组 (numpy array, shape: H x W x 3)
    """
    # 处理无效值（如果有的话）
    valid_mask = np.isfinite(dsm_array)

    if not np.any(valid_mask):
        # 如果全是无效值，返回黑色图像
        return np.zeros((*dsm_array.shape, 3), dtype=np.uint8)
    
    # 获取有效值的范围
    min_val = np.min(dsm_array[valid_mask])
    max_val = np.max(dsm_array[valid_mask])
    
    # 避免除零
    if max_val == min_val:
        normalized = np.zeros_like(dsm_array)
    else:
        # 归一化到0-1范围
        normalized = (dsm_array - min_val) / (max_val - min_val)
        # 处理无效值
        normalized[~valid_mask] = 0
    
    # 应用不同的颜色映射
    if colormap == 'jet':
        # 蓝-青-绿-黄-红 渐变
        rgb_image = np.zeros((*dsm_array.shape, 3))
        rgb_image[:,:,0] = np.clip(np.minimum(4*normalized-1.5, -4*normalized+4.5), 0, 1)  # Red
        rgb_image[:,:,1] = np.clip(np.minimum(4*normalized-0.5, -4*normalized+3.5), 0, 1)  # Green
        rgb_image[:,:,2] = np.clip(np.minimum(4*normalized+0.5, -4*normalized+2.5), 0, 1)  # Blue

        
    elif colormap == 'thermal':
        # 经典热成像色彩：黑色-深蓝-紫色-红色-黄色-白色
        rgb_image = np.zeros((*dsm_array.shape, 3))
        
        # 阶段1: 黑色到深蓝 (0-0.2)
        mask1 = normalized < 0.2
        progress = normalized[mask1] / 0.2
        rgb_image[mask1, 0] = 0.0  # Red: 0
        rgb_image[mask1, 1] = 0.0  # Green: 0
        rgb_image[mask1, 2] = progress * 0.5  # Blue: 0 -> 0.5
        
        # 阶段2: 深蓝到紫色 (0.2-0.4)
        mask2 = (normalized >= 0.2) & (normalized < 0.4)
        progress = (normalized[mask2] - 0.2) / 0.2
        rgb_image[mask2, 0] = progress * 0.5  # Red: 0 -> 0.5
        rgb_image[mask2, 1] = 0.0  # Green: 0
        rgb_image[mask2, 2] = 0.5 + progress * 0.3  # Blue: 0.5 -> 0.8
        
        # 阶段3: 紫色到红色 (0.4-0.6)
        mask3 = (normalized >= 0.4) & (normalized < 0.6)
        progress = (normalized[mask3] - 0.4) / 0.2
        rgb_image[mask3, 0] = 0.5 + progress * 0.5  # Red: 0.5 -> 1.0
        rgb_image[mask3, 1] = 0.0  # Green: 0
        rgb_image[mask3, 2] = 0.8 - progress * 0.8  # Blue: 0.8 -> 0
        
        # 阶段4: 红色到黄色 (0.6-0.8)
        mask4 = (normalized >= 0.6) & (normalized < 0.8)
        progress = (normalized[mask4] - 0.6) / 0.2
        rgb_image[mask4, 0] = 1.0  # Red: 1.0
        rgb_image[mask4, 1] = progress  # Green: 0 -> 1.0
        rgb_image[mask4, 2] = 0.0  # Blue: 0
        
        # 阶段5: 黄色到白色 (0.8-1.0)
        mask5 = normalized >= 0.8
        progress = (normalized[mask5] - 0.8) / 0.2
        rgb_image[mask5, 0] = 1.0  # Red: 1.0
        rgb_image[mask5, 1] = 1.0  # Green: 1.0
        rgb_image[mask5, 2] = progress  # Blue: 0 -> 1.0

    else:  # 默认灰度
        rgb_image = np.stack([normalized] * 3, axis=-1)
    
    # 转换为0-255的uint8格式
    rgb_image = (rgb_image * 255).astype(np.uint8)
    
    return rgb_image

def Label2RGB(label, COLOR_MAP):
    height, width = label.shape[0], label.shape[1]
    temp_mask = np.zeros(shape=(height, width))
    temp_mask = np.stack([temp_mask]*3,axis=-1)
    for index, color in enumerate(COLOR_MAP):
        locations = label==index
        locations = np.stack([locations]*3, axis=-1)
        temp_mask = np.where(locations, color, temp_mask)
    return temp_mask.astype(dtype=np.uint8)

def RGB2Label(label, COLOR_MAP):
    height, width = label.shape[0], label.shape[1]
    temp_mask = np.zeros(shape=(height, width))
    for index, color in enumerate(COLOR_MAP):
        locations = np.all(label == color, axis=-1)
        temp_mask[locations] = index
    return temp_mask.astype(dtype=np.int8)


class Vaihingen:
    def __init__(self, dataset_path, target_path):
        self.dataset_path = dataset_path
        self.target_path = target_path
        self.DSM_path = os.path.join(dataset_path, 'DSM')
        self.RGB_path = os.path.join(dataset_path, 'RGB')
        self.Label_path = os.path.join(dataset_path, 'Label')
        self.file_flag = os.listdir(self.Label_path)

    def start_dealWith(self, split_size, cover_size):
        # 创建目标目录
        os.makedirs(os.path.join(self.target_path, 'DSM'), exist_ok=True)
        os.makedirs(os.path.join(self.target_path, 'RGB'), exist_ok=True)
        os.makedirs(os.path.join(self.target_path, 'Label'), exist_ok=True)
        
        num_tif = 0
        num = 0
        tqdm_flag = tqdm.tqdm(self.file_flag, total=len(self.file_flag))
        for file in tqdm_flag:
            print(f'Processing file: {file}')
            #进行数据的读取
            image = np.array(Image.open(os.path.join(self.RGB_path, file)))
            dsm = np.array(Image.open(os.path.join(self.DSM_path, 'dsm_09cm_matching_'+ file.split('_')[-1].split('.')[0] + '.tif')))
            label = np.array(Image.open(os.path.join(self.Label_path, file)))
            
            # 将像素值进行对应的转换
            mask = RGB2Label(label=label, COLOR_MAP=Vaihingen_COLOR_MAP)
            # 开始进行切割
            # cover_size = 256
            min_x = min(image.shape[0], dsm.shape[0], mask.shape[0])
            min_y = min(image.shape[1], dsm.shape[1], mask.shape[1])
            range_x = ((min_x-split_size) // (split_size-cover_size) ) +1
            range_y = ((min_y-split_size) // (split_size-cover_size) ) +1

            #原先版本，无重叠切割
            # for x in range(range_x):
            #     for y in range(range_y):
            #         split_dsm = dsm[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         split_image = image[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         split_mask = mask[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         # Image.fromarray(split_dsm).save(os.path.join(self.target_path, 'DSM', str(num) + '.tif'))
            #         # Image.fromarray(split_image).save(os.path.join(self.target_path, 'RGB', str(num) + '.png'))
            #         # Image.fromarray(split_mask).save(os.path.join(self.target_path, 'Label', str(num) + '.png'))
            #         num += 1
            # num_tif += (x+1)*(y+1)

            for x in range(range_x):
                for y in range(range_y):
                    split_dsm = dsm[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    split_image = image[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    split_mask = mask[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    Image.fromarray(split_dsm).save(os.path.join(self.target_path, 'DSM', str(num) + '.tif'))
                    Image.fromarray(split_image).save(os.path.join(self.target_path, 'RGB', str(num) + '.png'))
                    Image.fromarray(split_mask).save(os.path.join(self.target_path, 'Label', str(num) + '.png'))
                    num += 1
            num_tif += (x+1)*(y+1)


        print(f'the number of png is {num_tif}')
        tqdm_flag.close()

class Potsdam:
    def __init__(self, dataset_path, target_path):
        self.dataset_path = dataset_path
        self.target_path = target_path
        self.DSM_path = os.path.join(dataset_path, 'DSM')
        self.RGB_path = os.path.join(dataset_path, 'RGB')
        self.Label_path = os.path.join(dataset_path, 'Label')
        self.file_flag = os.listdir(self.Label_path)

    def start_dealWith(self, split_size, cover_size):
        # 创建目标目录
        os.makedirs(os.path.join(self.target_path, 'DSM'), exist_ok=True)
        os.makedirs(os.path.join(self.target_path, 'RGB'), exist_ok=True)
        os.makedirs(os.path.join(self.target_path, 'Label'), exist_ok=True)


        regex = re.compile(r'(\d+)_(\d+)')
        num_tif = 0
        num = 0

        tqdm_flag = tqdm.tqdm(self.file_flag, total=len(self.file_flag))
        for file in tqdm_flag:
            print(f'Processing file: {file}')
            #进行数据的读取
            result = regex.search(file)
            if result:
                dsm_path = fr'dsm_potsdam_{int(result.group(1)):02d}_{int(result.group(2)):02d}.tif'
                rgb_path = fr'top_potsdam_{result.group()}_RGB.tif'
                label_path = file

            image = np.array(Image.open(os.path.join(self.RGB_path, rgb_path)))
            dsm = np.array(Image.open(os.path.join(self.DSM_path, dsm_path)))
            label = np.array(Image.open(os.path.join(self.Label_path, label_path)))
            
            # 将像素值进行对应的转换
            #mask = RGB2Label(label=label, COLOR_MAP=Vaihingen_COLOR_MAP)
            # 开始进行切割
            #cover_size = 256
            # min_x = min(image.shape[0], dsm.shape[0], mask.shape[0])
            # min_y = min(image.shape[1], dsm.shape[1], mask.shape[1])
            min_x = min(image.shape[0], dsm.shape[0], label.shape[0])
            min_y = min(image.shape[1], dsm.shape[1], label.shape[1])
            range_x = ((min_x-split_size) // (split_size-cover_size) ) +1  #方块可移动的距离除以每次移动的距离，得出第二个方块及以后的数量，最终数量要加上第一个方块
            range_y = ((min_y-split_size) // (split_size-cover_size) ) +1

            #原先版本，无重叠切割
            # for x in range(range_x):
            #     for y in range(range_y):
            #         split_dsm = dsm[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         split_image = image[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         split_mask = mask[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         # Image.fromarray(split_dsm).save(os.path.join(self.target_path, 'DSM', str(num) + '.tif'))
            #         # Image.fromarray(split_image).save(os.path.join(self.target_path, 'RGB', str(num) + '.png'))
            #         # Image.fromarray(split_mask).save(os.path.join(self.target_path, 'Label', str(num) + '.png'))
            #         num += 1
            # num_tif += (x+1)*(y+1)

            for x in range(range_x):
                for y in range(range_y):
                    split_dsm = dsm[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    split_image = image[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    split_mask = label[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    Image.fromarray(split_dsm).save(os.path.join(self.target_path, 'DSM', str(num) + '.tif'))
                    Image.fromarray(split_image).save(os.path.join(self.target_path, 'RGB', str(num) + '.png'))
                    Image.fromarray(split_mask).save(os.path.join(self.target_path, 'Label', str(num) + '.png'))
                    num += 1
            num_tif += (x+1)*(y+1)


        print(f'the number of png is {num_tif}')
        tqdm_flag.close()

class Gamus:
    def __init__(self, dataset_path, target_path):
        self.dataset_path = dataset_path
        self.target_path = target_path
        self.DSM_path = os.path.join(dataset_path, 'DSM')
        self.RGB_path = os.path.join(dataset_path, 'RGB')
        self.Label_path = os.path.join(dataset_path, 'Label')
        self.file_flag = os.listdir(self.Label_path)

    def start_dealWith(self, split_size, cover_size):
        # 创建目标目录
        os.makedirs(os.path.join(self.target_path, 'DSM'), exist_ok=True)
        os.makedirs(os.path.join(self.target_path, 'RGB'), exist_ok=True)
        os.makedirs(os.path.join(self.target_path, 'Label'), exist_ok=True)


        regex = re.compile(r'(.*_)(\w+)\.(\w+)')
        num_tif = 0
        num = 0

        tqdm_flag = tqdm.tqdm(self.file_flag, total=len(self.file_flag))
        for file in tqdm_flag:
            print(f'Processing file: {file}')
            #进行数据的读取
            result = regex.search(file)
            if result:
                dsm_path = fr'{result.group(1)}AGL.png'
                rgb_path_1 = fr'{result.group(1)}RGB.jpg'
                rgb_path_2 = fr'{result.group(1)}IMG.jpg'
                if os.path.exists(os.path.join(self.RGB_path,rgb_path_1)):
                    rgb_path = rgb_path_1
                elif os.path.exists(os.path.join(self.RGB_path,rgb_path_2)):
                    rgb_path = rgb_path_2
                else:
                    print(f"{rgb_path_1}不存在")
                label_path = file

            image = np.array(Image.open(os.path.join(self.RGB_path, rgb_path)))
            dsm = np.array(Image.open(os.path.join(self.DSM_path, dsm_path)))
            label = np.array(Image.open(os.path.join(self.Label_path, label_path)))

            
            # 将像素值进行对应的转换
            #mask = RGB2Label(label=label, COLOR_MAP=Vaihingen_COLOR_MAP)
            # 开始进行切割
            #cover_size = 256
            # min_x = min(image.shape[0], dsm.shape[0], mask.shape[0])
            # min_y = min(image.shape[1], dsm.shape[1], mask.shape[1])
            min_x = min(image.shape[0], dsm.shape[0], label.shape[0])
            min_y = min(image.shape[1], dsm.shape[1], label.shape[1])
            range_x = ((min_x-split_size) // (split_size-cover_size) ) +1  #方块可移动的距离除以每次移动的距离，得出第二个方块及以后的数量，最终数量要加上第一个方块
            range_y = ((min_y-split_size) // (split_size-cover_size) ) +1
            print(range_x)

            #原先版本，无重叠切割
            # for x in range(range_x):
            #     for y in range(range_y):
            #         split_dsm = dsm[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         split_image = image[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         split_mask = mask[x * split_size:(x + 1) * split_size, y * split_size:(y + 1) * split_size]
            #         # Image.fromarray(split_dsm).save(os.path.join(self.target_path, 'DSM', str(num) + '.tif'))
            #         # Image.fromarray(split_image).save(os.path.join(self.target_path, 'RGB', str(num) + '.png'))
            #         # Image.fromarray(split_mask).save(os.path.join(self.target_path, 'Label', str(num) + '.png'))
            #         num += 1
            # num_tif += (x+1)*(y+1)

            for x in range(range_x):
                for y in range(range_y):
                    split_dsm = dsm[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    split_image = image[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    split_mask = label[x * (split_size-cover_size):x * (split_size-cover_size) + split_size, y * (split_size-cover_size):y * (split_size-cover_size) + split_size]
                    Image.fromarray(split_dsm).save(os.path.join(self.target_path, 'DSM', str(num) + '.png'))
                    Image.fromarray(split_image).save(os.path.join(self.target_path, 'RGB', str(num) + '.jpg'))
                    Image.fromarray(split_mask).save(os.path.join(self.target_path, 'Label', str(num) + '.png'))
                    num += 1
            num_tif += (x+1)*(y+1)


        print(f'the number of png is {num_tif}')
        tqdm_flag.close()

class Visual_RGB:
    def __init__(self, dataset_path, target_path):
        self.dataset_path = dataset_path
        self.target_path = target_path
        self.DSM_path = os.path.join(dataset_path, 'DSM')
        self.Label_path = os.path.join(dataset_path, 'Label')
        self.Label_flag = os.listdir(self.Label_path)
        self.DSM_flag = os.listdir(self.DSM_path)
 
    def Label2RGB(self):
        os.makedirs(os.path.join(self.target_path, 'Label_RGB'), exist_ok=True)
        tqdm_flag = tqdm.tqdm(self.Label_flag,total=len(self.Label_flag))
        for file in tqdm_flag:
            label_np = np.array(Image.open(os.path.join(self.Label_path, file)))
            rgb_image = Label2RGB(label_np, Vaihingen_COLOR_MAP)
            Image.fromarray(rgb_image).save(os.path.join(self.target_path, 'Label_RGB', file.replace('.png', '_rgb.png')))
            print(f"Label RGB visualization saved for {file}")
        tqdm_flag.close()

    def DSM2RGB(self):
        os.makedirs(os.path.join(self.target_path,'DSM_RGB'), exist_ok=True)
        tqdm_flag = tqdm.tqdm(self.DSM_flag,total=len(self.DSM_flag))
        for file in tqdm_flag:
            dsm = np.array(Image.open(os.path.join(self.DSM_path, file)))
            rgb_image = DSM2RGB(dsm, colormap='thermal')
            Image.fromarray(rgb_image).save(os.path.join(self.target_path, 'DSM_RGB', file.replace('.tif', '_dsm_rgb.png')))
            print(f"DSM RGB visualization saved for {file}")
        tqdm_flag.close()



class Rename: 
    def __init__(self, dataset_path):
        self.dataset_path = dataset_path
        self.DSM_path = os.path.join(dataset_path, 'ndsm')
        self.RGB_path = os.path.join(dataset_path, 'image')
        self.Label_path = os.path.join(dataset_path, 'mask')
        self.file_flag = sorted(os.listdir(self.Label_path),key=lambda x : int(x.split('_')[1]))

    
    def rename(self,mode):

        tqdm_flag = tqdm.tqdm(self.file_flag,total = len(self.file_flag))
        for file in tqdm_flag:
            i = file.split('_')[1]
            if mode == 'RGB'or mode =='all':
                old_path_RGB = os.path.join(self.RGB_path,f'scene_{int(i):04d}_IMG.png')
                if os.path.exists(old_path_RGB):
                    
                    new_name_RGB = f'scene_{int(i):04d}_IMG.tif'
                    new_path_RGB = os.path.join(self.RGB_path,new_name_RGB)
                    os.rename(old_path_RGB,new_path_RGB)
                    print(f"Processing img  {old_path_RGB} to {new_path_RGB}")

            if mode == 'Label'or mode =='all':
                old_path_Label = os.path.join(self.Label_path,f'scene_{int(i):04d}_BLG.png')
                if os.path.exists(old_path_Label):
                    new_name_Label = f'scene_{int(i):04d}_BLG.tif'
                    new_path_Label = os.path.join(self.Label_path,new_name_Label)
                    os.rename(old_path_Label,new_path_Label)
                    print(f"Processing label  {old_path_Label} to {new_path_Label}")

            # if mode == 'DSM'or mode =='all':
            #     old_path_DSM = os.path.join(self.DSM_path,f'{i}.tif')
            #     if os.path.exists(old_path_DSM):
            #         new_name_DSM = f'scene_{int(i):04d}_AGL.tif'
            #         new_path_DSM = os.path.join(self.DSM_path,new_name_DSM)
            #         os.rename(old_path_DSM,new_path_DSM)
            #         print(f"Processing dsm  {old_path_DSM} to {new_path_DSM}")

def main():
    pass

    #预处理
    # v = Vaihingen(dataset_path='/home/proof/hjl/Vaihingen/Vaihingen',
    #               target_path='/home/proof/hjl/HTC-DC-Net-main/data')
    # v.start_dealWith(split_size=512,cover_size=256)

    g = Gamus(dataset_path='/home/proof/hjl/dataset/tmp',
                  target_path='/home/proof/hjl/dataset/Gamus_split')
    g.start_dealWith(split_size=512,cover_size=256)

    #可视化label和dsm
    # r = Visual_RGB(dataset_path='/home/proof/hjl/HTC-DC-Net-main/data',
    #               target_path='/home/proof/hjl/HTC-DC-Net-main/data')
    # r.Label2RGB()
    # r.DSM2RGB()
    
    #文件重命名
    # n = Rename('/home/proof/hjl/HTC-DC-Net-main/data')
    # n.rename('all')




if __name__ == '__main__':
    main()