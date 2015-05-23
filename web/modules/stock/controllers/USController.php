<?php

/**
 * @desc 美股特别分析
 * @author fox
 * @date 2015/04/28
 *
 */
class USController extends Controller
{
	/**
	 * @desc 中概股数据总览
	 * @param $_GET['day'] 可选
	 */
	public function actionCnlist()
	{
		$day = isset($_GET['day'])? intval($_GET['day']) : CommonUtil::getUSDay();
		$cnCodeList = Yii::app()->params['cnlist'];
		$cnStockMap = array();
		
		$code2idmap = StockUtil::getStockMap(CommonUtil::LOCATION_US);
		foreach ($cnCodeList as $code)
		{
			if (!isset($code2idmap[$code]))
			{
				continue;
			}
			
			$sid = $code2idmap[$code];	
			$poolInfo = DataModel::getPoolInfo($sid, $day, CommonUtil::SOURCE_CONT|CommonUtil::SOURCE_PRICE_THRESHOLD|CommonUtil::SOURCE_UP_RESIST);
			$cnStockMap[$sid] = $poolInfo;
		}
		
		$this->render('cnlist', array(
				'day' => $day,
				'poolList' => $cnStockMap,
		));
	}
}
?>