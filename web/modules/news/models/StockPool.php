<?php

/**
 * This is the model class for table "t_stock_pool".
 *
 * The followings are the available columns in table 't_stock_pool':
 * @property string $id
 * @property integer $sid
 * @property string $name
 * @property integer $day
 * @property integer $reason
 * @property integer $worth
 * @property string $current_price
 * @property string $low_price
 * @property string $high_price
 * @property integer $create_time
 * @property string $status
 */
class StockPool extends CActiveRecord
{
	/**
	 * Returns the static model of the specified AR class.
	 * @return StockPool the static model class
	 */
	public static function model($className=__CLASS__)
	{
		return parent::model($className);
	}

	/**
	 * @return string the associated database table name
	 */
	public function tableName()
	{
		return 't_stock_pool';
	}

	/**
	 * @return array validation rules for model attributes.
	 */
	public function rules()
	{
		// NOTE: you should only define rules for those attributes that
		// will receive user inputs.
		return array(
			array('sid, day, reason, worth, create_time', 'numerical', 'integerOnly'=>true),
			array('name', 'length', 'max'=>32),
			array('current_price, low_price, high_price', 'length', 'max'=>6),
			array('status', 'length', 'max'=>1),
			// The following rule is used by search().
			// Please remove those attributes that should not be searched.
			array('id, sid, name, day, reason, worth, current_price, low_price, high_price, create_time, status', 'safe', 'on'=>'search'),
		);
	}

	/**
	 * @return array relational rules.
	 */
	public function relations()
	{
		// NOTE: you may need to adjust the relation name and the related
		// class name for the relations automatically generated below.
		return array(
		);
	}

	/**
	 * @return array customized attribute labels (name=>label)
	 */
	public function attributeLabels()
	{
		return array(
			'id' => 'Id',
			'sid' => 'Sid',
			'name' => 'Name',
			'day' => 'Day',
			'reason' => 'Reason',
			'worth' => 'Worth',
			'current_price' => 'Current Price',
			'low_price' => 'Low Price',
			'high_price' => 'High Price',
			'create_time' => 'Create Time',
			'status' => 'Status',
		);
	}

	/**
	 * Retrieves a list of models based on the current search/filter conditions.
	 * @return CActiveDataProvider the data provider that can return the models based on the search/filter conditions.
	 */
	public function search()
	{
		// Warning: Please modify the following code to remove attributes that
		// should not be searched.

		$criteria=new CDbCriteria;

		$criteria->compare('id',$this->id,true);

		$criteria->compare('sid',$this->sid);

		$criteria->compare('name',$this->name,true);

		$criteria->compare('day',$this->day);

		$criteria->compare('reason',$this->reason);

		$criteria->compare('worth',$this->worth);

		$criteria->compare('current_price',$this->current_price,true);

		$criteria->compare('low_price',$this->low_price,true);

		$criteria->compare('high_price',$this->high_price,true);

		$criteria->compare('create_time',$this->create_time);

		$criteria->compare('status',$this->status,true);

		return new CActiveDataProvider('StockPool', array(
			'criteria'=>$criteria,
		));
	}
}